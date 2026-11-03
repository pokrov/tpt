"""Scheduled varied workbooks honor actual grade selection, failure isolation and metadata."""
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cron_job
from core.paths import CALENDAR_PATH
from core.theme_picker import pick_daily_book_specs


class ScheduledBatchTests(unittest.TestCase):
    def test_fixed_grade_avoids_recent_pairs_for_that_actual_grade(self):
        calendar = {'events':[{'event_name':'Test event','schedule':{'kind':'fixed','month':11,'day':5},
                              'theme_angles':['Recent angle','Fresh angle']}]}
        state = {'generated':[{'theme':'Recent angle','grade_band':'5th-6th','generated_on':'2026-10-26'}]}
        for _ in range(5):
            first = pick_daily_book_specs(calendar,state,count=1,today=date(2026,10,27),grade_band='5th-6th')[0]
            self.assertEqual(first['grade_band'],'5th-6th')
            self.assertEqual(first['theme'],'Fresh angle')
        specs = pick_daily_book_specs(calendar,{},count=5,today=date(2026,10,27),grade_band='3rd-4th')
        self.assertEqual({s['grade_band'] for s in specs},{'3rd-4th'})

    def test_varied_batch_keeps_success_when_a_later_book_fails(self):
        with TemporaryDirectory() as folder:
            state_path = Path(folder)/'state.json'
            specs=[dict(event_name='Halloween',theme='Read and solve',grade_band='5th-6th',
                book_title='Halloween',calendar_note='',event_date='2026-10-31',event_end='2026-10-31',
                selection_mode='upcoming_event',title_keyword='',selection_window_start='2026-10-27',
                selection_window_end='2026-11-26')]*2
            good_pdf=Path(folder)/'good.pdf';good_pdf.write_bytes(b'%PDF-test')
            with patch.object(cron_job,'validate_providers'),patch.object(cron_job,'fetch_library_state',return_value=None), \
                 patch.object(cron_job,'load_state',return_value={'generated':[],'local_schedule':{'enabled':False}}), \
                 patch.object(cron_job,'STATE_PATH',state_path), \
                 patch.object(cron_job,'pick_daily_book_specs',return_value=specs) as choose, \
                 patch.object(cron_job,'deliver_book',return_value=False), \
                 patch.object(cron_job,'commit_state_to_github',return_value=(False,'Disabled in test')), \
                 patch.object(cron_job,'generate_book',side_effect=[({'title':'Halloween'},good_pdf),ValueError('Test item failed')]) as generate:
                code=cron_job.main(count=2,book_type='varied_activities',grade_band='5th-6th',
                                   reference_date=date(2026,10,20))
            self.assertEqual(code,1)
            self.assertTrue(good_pdf.exists())
            state=json.loads(state_path.read_text())
            self.assertEqual(len(state['generated']),1)
            self.assertEqual(state['generated'][0]['book_type'],'varied_activities')
            self.assertIn('local_schedule',state)
            self.assertEqual(choose.call_args.kwargs['grade_band'],'5th-6th')
            self.assertEqual(generate.call_args.kwargs['book_type'],'varied_activities')

    def test_invalid_options_never_spend_provider_quota(self):
        for options in [{'count':0},{'count':True},{'grade_band':'1st-2nd'},{'book_type':'invalid'}]:
            with patch.object(cron_job,'validate_providers') as provider:
                self.assertEqual(cron_job.main(**options),2)
                provider.assert_not_called()
