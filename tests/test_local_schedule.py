"""Scheduling is deterministic, restart-safe and independent of provider credentials."""
from datetime import datetime
import os
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ['LOCAL_SCHEDULER_THREAD'] = '0'

from core.local_schedule import validate_schedule, schedule_due, next_run
from tests.test_local_server import LocalServerTests
import local_server as local


def settings(**changes):
    return {**dict(enabled=True, frequency='weekly', weekday=1, time='09:00',
        timezone='Africa/Casablanca', count=2, book_type='varied_activities',
        grade_band='5th-6th'), **changes}


class ScheduleLogicTests(unittest.TestCase):
    def now(self, day=27, hour=10):
        return datetime(2026, 10, day, hour, tzinfo=ZoneInfo('Africa/Casablanca'))

    def test_weekly_only_runs_on_selected_day_after_time(self):
        config = settings()
        self.assertTrue(schedule_due(self.now(), {}, config))
        self.assertFalse(schedule_due(self.now(hour=8), {}, config))
        self.assertFalse(schedule_due(self.now(day=28), {}, config))
        self.assertFalse(schedule_due(self.now(), {}, settings(enabled=False)))
        self.assertTrue(schedule_due(self.now(day=28), {}, settings(frequency='daily')))

    def test_failed_interrupted_or_completed_attempt_does_not_repeat(self):
        for extra in ({}, {'exit_code': 1}, {'exit_code': 0}):
            state = {'local_daily': {'attempted_on': '2026-10-27', **extra}}
            self.assertFalse(schedule_due(self.now(), state, settings()))
            self.assertTrue(next_run(self.now(), state, settings()).startswith('2026-11-03T09:00'))

    def test_timezone_conversion_and_year_boundary(self):
        utc = datetime(2026, 10, 27, 23, 30, tzinfo=ZoneInfo('UTC'))
        config = settings(frequency='daily', time='00:15', timezone='Asia/Tokyo')
        self.assertFalse(schedule_due(utc, {'local_daily': {'attempted_on':'2026-10-28'}}, config))
        self.assertTrue(schedule_due(utc, {}, config))
        next_slot = next_run(datetime(2026,12,31,23,tzinfo=ZoneInfo('UTC')), {},
                             settings(weekday=0,timezone='UTC'))
        self.assertTrue(next_slot.startswith('2027-01-04T09:00'))

    def test_dst_wall_clock_stays_at_selected_hour(self):
        config = settings(frequency='daily', timezone='Europe/Paris')
        before = datetime(2026,3,28,10,tzinfo=ZoneInfo('Europe/Paris'))
        state = {'local_daily':{'attempted_on':'2026-03-28'}}
        self.assertEqual(next_run(before,state,config),'2026-03-29T09:00+02:00')

    def test_rejects_malformed_settings_without_coercion(self):
        for key, value in [('enabled','yes'), ('weekday',True), ('weekday',7), ('count',True),
                           ('count',21), ('count',0), ('time','25:00'), ('timezone','Not/AZone'),
                           ('book_type',[]), ('grade_band','1st-2nd'), ('frequency','hourly')]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                validate_schedule(settings(**{key:value}))
        with self.assertRaises(ValueError):
            validate_schedule({'enabled':True})


class ScheduleApiTests(LocalServerTests):
    def test_save_survives_reload_and_preserves_history_and_markers(self):
        original = {'generated':[{'title':'Keep me'}], 'local_daily':{'attempted_on':'2026-10-26'}}
        self.save(original)
        result = self.client.put('/local/schedule',json=settings())
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.load()['generated'],original['generated'])
        self.assertEqual(self.load()['local_daily'],original['local_daily'])
        self.assertEqual(self.client.get('/local/schedule').json['settings'], settings())
        page = self.client.get('/').get_data(as_text=True)
        for label in ['Automatic workbook worker','Every week','schedule-time','schedule-count']:
            self.assertIn(label,page)

    def test_auth_validation_and_cross_origin_write_protection(self):
        with patch.dict(os.environ,WEBHOOK_API_KEY='test-only'):
            self.assertEqual(self.client.put('/local/schedule',json=settings()).status_code,401)
            self.assertEqual(self.client.get('/local/schedule').status_code,401)
        self.assertEqual(self.client.put('/local/schedule',json=settings(count=0)).status_code,400)
        self.assertEqual(self.client.put('/local/schedule',data='text').status_code,415)
        self.assertEqual(self.client.put('/local/schedule',json=settings(),
            headers={'Origin':'https://another-site.invalid'}).status_code,403)
        self.assertNotIn('local_schedule',self.load())

    def test_busy_worker_cannot_lose_state_when_settings_are_saved(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        acquired, release = Event(), Event()
        def hold():
            with local.GENERATION_LOCK:
                acquired.set(); release.wait(3)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(hold)
            self.assertTrue(acquired.wait(1))
            try:
                self.assertEqual(self.client.put('/local/schedule',json=settings()).status_code,409)
            finally:
                release.set()
            future.result()

    def test_run_now_uses_saved_type_grade_and_count_with_schedule_disabled(self):
        config = settings(enabled=False)
        self.client.put('/local/schedule',json=config)
        with patch.object(local.web._job_worker,'submit') as submit:
            response = self.client.post('/local/daily-run')
        self.assertEqual(response.status_code,202)
        self.assertEqual(submit.call_args.args[2],config)
        with patch.object(local.cron_job,'main',return_value=0) as batch:
            local.perform_daily(response.json['job_id'],config)
        self.assertEqual(batch.call_args.kwargs['book_type'],'varied_activities')
        self.assertEqual(batch.call_args.kwargs['grade_band'],'5th-6th')
        self.assertEqual(batch.call_args.kwargs['count'],2)
        self.assertIn('reference_date',batch.call_args.kwargs)

    def test_queued_schedule_is_rechecked_after_pause_or_previous_attempt(self):
        config = settings(frequency='daily',time='00:00')
        self.save({**self.load(),'local_schedule':config})
        with patch.object(local.web._job_worker,'submit'):
            response = local.queue_daily(config,scheduled=True)
        state = self.load(); state['local_schedule']['enabled'] = False; self.save(state)
        with patch.object(local.cron_job,'main') as batch:
            local.perform_daily(response['job_id'],config,scheduled=True)
        batch.assert_not_called()
        self.assertNotIn('local_daily',self.load())
