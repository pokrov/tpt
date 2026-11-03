"""Local web entry point: shared storage, serialized generation and optional daily batches."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
from threading import Event, RLock, Thread
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import jsonify, request

import cron_job
import webhook_server as web
from core.state_manager import load_state, save_state
from core.local_schedule import validate_schedule, schedule_due, next_run
from core.runtime import int_setting

app = web.app
from core.workbook_v2_web import bp as workbook_v2_blueprint
app.register_blueprint(workbook_v2_blueprint)
LOGGER = logging.getLogger(__name__)
GENERATION_LOCK = RLock()
_original_generation = web.run_generation


def serialized_generation(brief):
    """Share one generation/state-write lock between local batches and web requests."""
    with GENERATION_LOCK:
        return _original_generation(brief)


web.run_generation = serialized_generation


def schedule_settings():
    """Validate the opt-in local schedule without contacting any AI service."""
    enabled = os.getenv('LOCAL_AUTO_DAILY', '0')
    clock = os.getenv('LOCAL_DAILY_TIME', '09:00')
    if enabled not in {'0', '1'}:
        raise ValueError('LOCAL_AUTO_DAILY must be 0 or 1')
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', clock):
        raise ValueError('LOCAL_DAILY_TIME must use HH:MM, for example 09:00')
    return enabled == '1', clock, ZoneInfo(os.getenv('BOOK_TIMEZONE', 'Africa/Casablanca'))


@app.context_processor
def local_context():
    """Expose local controls only when this entry point serves the existing dashboard."""
    settings = current_schedule()
    return dict(local_mode=True, local_schedule=settings,
                local_daily_schedule=(settings['time']+' '+settings['timezone']) if settings['enabled'] else 'Manual only')


def current_schedule(state=None):
    """Use saved web settings, falling back to legacy environment settings."""
    state = load_state() if state is None else state
    if 'local_schedule' in state:
        return validate_schedule(state['local_schedule'])
    enabled, clock, zone = schedule_settings()
    return validate_schedule(dict(enabled=enabled, frequency='daily', weekday=0, time=clock,
        timezone=str(zone), count=int_setting('DAILY_BOOK_COUNT', 1, 1, 20), book_type='reading_qcm', grade_band='rotate'))


@app.route('/local/schedule', methods=['GET', 'PUT'])
def schedule_api():
    """Save schedule settings atomically without overwriting a running book's history."""
    if not web._authorized():
        return jsonify(error='Unauthorized. Supply the generation access key.'), 401
    if request.method == 'PUT':
        if not request.is_json:
            return jsonify(error='Request body must be JSON.'), 415
        # This browser-only mutation needs same-origin protection even without an access key.
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='Save the schedule from this application page.'), 403
        try:
            settings = validate_schedule(request.get_json(silent=True))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if not GENERATION_LOCK.acquire(blocking=False):
            return jsonify(error='A workbook is running. Wait until it finishes before saving the schedule.'), 409
        try:
            state = load_state()
            state['local_schedule'] = settings
            save_state(state)
        finally:
            GENERATION_LOCK.release()
    state = load_state()
    settings = current_schedule(state)
    response = jsonify(settings=settings,
        next_run=next_run(datetime.now(timezone.utc), state, settings),
        last_run=state.get('local_daily', {}))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/local/worker-status')
def worker_status():
    """Expose only queue activity so maintenance can avoid interrupting generation."""
    if not web._authorized():
        return jsonify(error='Unauthorized.'), 401
    with web._jobs_lock:
        active = sum(j['status'] in {'queued', 'running'} for j in web._jobs.values())
    acquired = GENERATION_LOCK.acquire(blocking=False)
    if acquired:
        GENERATION_LOCK.release()
    return jsonify(active_jobs=active, generation_busy=not acquired)


def perform_daily(job_id, settings=None, scheduled=False):
    """Run the cron pipeline in this process and publish its outcome to the web job tracker."""
    with web._jobs_lock:
        web._jobs[job_id].update(status='running', message='Generating the daily batch. Completed PDFs appear in the library.')
    with GENERATION_LOCK:
        state = load_state()
        zone = ZoneInfo(settings['timezone']) if settings else schedule_settings()[2]
        now = datetime.now(zone)
        if scheduled and (current_schedule(state) != settings or not schedule_due(now, state, settings)):
            with web._jobs_lock:
                web._jobs[job_id].update(status='completed', book_count=0,
                    message='Scheduled run skipped: settings changed or today was already attempted.',
                    updated=time.monotonic())
            return
        today = now.date().isoformat()
        before = len(state['generated'])
        state['local_daily'] = dict(attempted_on=today, started_at=datetime.now().astimezone().isoformat())
        save_state(state)
        try:
            options = {} if settings is None else dict(count=settings['count'], book_type=settings['book_type'],
                grade_band=None if settings['grade_band'] == 'rotate' else settings['grade_band'],
                reference_date=now.date())
            exit_code = cron_job.main(**options)
            state = load_state()
            count = max(0, len(state['generated']) - before)
            state['local_daily'].update(exit_code=exit_code, completed_at=datetime.now().astimezone().isoformat())
            save_state(state)
            result = dict(status='completed' if exit_code == 0 else 'failed', book_count=count,
                message=f'Daily batch finished: {count} workbook(s) saved. Refresh the library.', library_url='/books')
            if exit_code:
                result.update(error='Some or all daily books failed. Completed PDFs remain in the library.',
                              detail='Open View Logs.cmd for the generation errors.')
        except Exception:
            LOGGER.exception('Local daily batch failed')
            result = dict(status='failed', error='Daily batch failed. Open View Logs.cmd for details.', library_url='/books')
    with web._jobs_lock:
        web._jobs[job_id].update(result, updated=time.monotonic())


def queue_daily(settings=None, scheduled=False):
    """Queue one batch using the same bounded worker as on-demand workbook generation."""
    with web._jobs_lock:
        active = [j for j in web._jobs.values() if j['status'] in {'queued', 'running'}]
        if len(active) >= 2 or any(j.get('kind') == 'daily' for j in active):
            return None
        job_id = uuid4().hex
        web._jobs[job_id] = dict(kind='daily', status='queued', message='Daily batch queued.', updated=time.monotonic())
        try:
            if settings is None and 'local_schedule' in load_state():
                settings = current_schedule()
            web._job_worker.submit(perform_daily, job_id, settings, scheduled)
        except RuntimeError:
            del web._jobs[job_id]
            return None
    return dict(status='queued', job_id=job_id, status_url='/generation-jobs/' + job_id)


@app.post('/local/daily-run')
def daily_run():
    """Start a manual batch from the local web interface without blocking its HTTP request."""
    if not web._authorized():
        return jsonify(error='Unauthorized. Supply the generation access key.'), 401
    result = queue_daily()
    if result is None:
        return jsonify(error='Generation is busy. Wait for the current books to finish.'), 429
    return jsonify(result), 202


def daily_due(now, state, clock):
    """Run at most one scheduled attempt per local date, including after a late startup."""
    return (now.strftime('%H:%M') >= clock
            and state.get('local_daily', {}).get('attempted_on') != now.date().isoformat())


def scheduler_loop(stop):
    """Check the opt-in schedule while the computer and local service are running."""
    while not stop.is_set():
        try:
            # Do not wait behind a long generation: the next tick can check it.
            if GENERATION_LOCK.acquire(blocking=False):
                try:
                    state = load_state()
                    settings = current_schedule(state)
                    if schedule_due(datetime.now(timezone.utc), state, settings):
                        queue_daily(settings, scheduled=True)
                finally:
                    GENERATION_LOCK.release()
        except Exception:
            LOGGER.exception('Could not check the local daily schedule')
        stop.wait(30)


# Always listen for saved web settings; a disabled schedule makes no AI requests.
# Set LOCAL_SCHEDULER_THREAD=0 only in isolated tests.
if os.getenv('LOCAL_SCHEDULER_THREAD', '1') == '1':
    Thread(target=scheduler_loop, args=(Event(),), daemon=True, name='local-daily-scheduler').start()
