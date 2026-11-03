"""Shared offline upload screen for the standalone and existing local apps."""
from functools import wraps
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from threading import Lock
from uuid import uuid4

from flask import Blueprint, abort, current_app, redirect, render_template, request, send_file, session, url_for

MAX_UPLOAD = 80 * 1024 * 1024
PROCESS_LOCK = Lock()


def create_blueprint(storage, library_dir=None):
    root = Path(storage)
    bp = Blueprint('offline_listing', __name__, template_folder='templates', url_prefix='/listing-tool')

    def library_root():
        value = library_dir() if callable(library_dir) else library_dir
        return Path(value).resolve() if value is not None else None

    def library_file(filename):
        base = library_root()
        if (base is None or not filename or len(filename)>220 or '/' in filename or '\\' in filename
                or not filename.lower().endswith('.pdf')):
            abort(404)
        path = base / filename
        if path.is_symlink() or path.resolve().parent != base or not path.is_file():
            abort(404)
        return path

    def folder(job):
        if not re.fullmatch(r'[a-f0-9]{32}', job):
            abort(404)
        directory = root / job
        if not (directory / 'book.json').is_file():
            abort(404)
        return directory

    def run(action, directory):
        result = subprocess.run([sys.executable, '-m', 'listing_tool.worker', action, str(directory.resolve())],
                                cwd=str(Path(__file__).resolve().parent.parent),
                                capture_output=True, text=True, timeout=300)
        if result.returncode:
            try:
                message = json.loads(result.stdout)['error']
            except (ValueError, KeyError):
                message = 'The offline PDF operation failed.'
            raise ValueError(message)

    @bp.before_request
    def protect():
        # This feature is deliberately local even when the main app has remote routes.
        if request.host.split(':')[0].lower() not in {'localhost', '127.0.0.1'}:
            abort(403, 'Open this tool through localhost or 127.0.0.1.')
        expected = os.environ.get('WEBHOOK_API_KEY', '')
        supplied = request.headers.get('X-API-Key', '')
        if request.authorization and request.authorization.type == 'basic':
            supplied = request.authorization.password or ''
        if expected and not hmac.compare_digest(supplied, expected):
            return 'Use your existing generation access key as the password.', 401, {'WWW-Authenticate': 'Basic realm="Local PDF tool"'}
        if 'listing_csrf' not in session:
            session['listing_csrf'] = secrets.token_hex(24)
        if request.method == 'POST':
            if not hmac.compare_digest(request.form.get('csrf', ''), session['listing_csrf']):
                abort(403, 'Refresh this page before submitting the form.')

    @bp.after_request
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    def screen(book=None, job=None, error=None, result=None, library=None, selected_file=None):
        return render_template('listing_tool.html', book=book, job=job, error=error,
                               result=result, csrf=session['listing_csrf'], library=library,
                               selected_file=selected_file, library_enabled=library_dir is not None)

    @bp.get('/')
    def index():
        return screen()

    @bp.get('/library')
    def library():
        base = library_root()
        if base is None:
            abort(404)
        files = sorted((p for p in base.glob('*.pdf') if p.is_file() and not p.is_symlink()),
                       key=lambda p:p.stat().st_mtime, reverse=True)
        return screen(library=[dict(filename=p.name, has_info=p.with_suffix('.product.json').is_file()) for p in files])

    @bp.route('/from-library/<filename>', methods=['GET','POST'])
    def from_library(filename):
        source = library_file(filename)
        if request.method == 'GET':
            return screen(selected_file=filename)
        if not PROCESS_LOCK.acquire(blocking=False):
            return screen(error='Another offline PDF is being processed. Try again shortly.', selected_file=filename), 409
        directory = root / uuid4().hex
        try:
            if source.stat().st_size > MAX_UPLOAD:
                raise ValueError('Choose a PDF smaller than 80 MB.')
            directory.mkdir(parents=True)
            shutil.copyfile(source, directory / 'original.pdf')
            metadata = source.with_suffix('.product.json')
            if metadata.is_file() and not metadata.is_symlink() and metadata.stat().st_size <= 2*1024*1024:
                shutil.copyfile(metadata, directory / 'product.json')
            run('inspect', directory)
            book = json.loads((directory/'book.json').read_text(encoding='utf-8'))
            # Known books can create all three outputs immediately; ambiguous legacy facts open review.
            if book.get('topic') and book.get('grade') in {'3-4','5-6'} and len(book.get('suggested',[])) == 3:
                options = dict(topic=book['topic'], grade=book['grade'], pages=','.join(map(str,book['suggested'])))
                (directory/'options.json').write_text(json.dumps(options),encoding='utf-8')
                run('build', directory)
            return redirect(url_for('.review', job=directory.name), code=303)
        except (ValueError, subprocess.TimeoutExpired) as exc:
            # Keep any successfully inspected job available for manual review, including its original.
            if (directory/'book.json').is_file():
                book = json.loads((directory/'book.json').read_text(encoding='utf-8'))
                return screen(book, directory.name, error=str(exc) if isinstance(exc,ValueError) else 'PDF processing timed out. Try a smaller PDF.'), 400
            if directory.exists():
                for item in directory.iterdir():
                    item.unlink()
                directory.rmdir()
            return screen(error=str(exc) if isinstance(exc,ValueError) else 'PDF processing timed out. Try a smaller PDF.', selected_file=filename), 400
        finally:
            PROCESS_LOCK.release()

    @bp.post('/upload')
    def upload():
        if request.content_length and request.content_length > MAX_UPLOAD + 1024 * 1024:
            return screen(error='Upload a PDF smaller than 80 MB.'), 413
        file = request.files.get('pdf')
        if not file:
            return screen(error='Choose a PDF file.'), 400
        if not PROCESS_LOCK.acquire(blocking=False):
            return screen(error='Another offline PDF is being processed. Try again shortly.'), 409
        directory = root / uuid4().hex
        try:
            directory.mkdir(parents=True)
            with (directory / 'original.pdf').open('wb') as handle:
                total = 0
                while chunk := file.stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD:
                        raise ValueError('Upload a PDF smaller than 80 MB.')
                    handle.write(chunk)
            with (directory / 'original.pdf').open('rb') as handle:
                if not handle.read(1024).lstrip().startswith(b'%PDF-'):
                    raise ValueError('Choose a valid PDF file.')
            run('inspect', directory)
            return redirect(url_for('.review', job=directory.name), code=303)
        except (ValueError, subprocess.TimeoutExpired) as exc:
            # Only remove this tool's new, failed upload; never workbook files.
            for item in directory.iterdir():
                item.unlink()
            directory.rmdir()
            message = str(exc) if isinstance(exc, ValueError) else 'PDF processing exceeded five minutes. Split this PDF into smaller files and try again.'
            return screen(error=message), 400
        finally:
            PROCESS_LOCK.release()

    @bp.route('/<job>', methods=['GET', 'POST'])
    def review(job):
        directory = folder(job)
        book = json.loads((directory / 'book.json').read_text(encoding='utf-8'))
        if request.method == 'POST':
            if not PROCESS_LOCK.acquire(blocking=False):
                return screen(book, job, error='Another offline PDF is being processed. Try again shortly.'), 409
            try:
                options = {key: request.form.get(key, '').strip() for key in ('topic', 'grade', 'pages')}
                if any(len(value) > 200 for value in options.values()):
                    raise ValueError('One of the fields is too long.')
                (directory / 'options.json').write_text(json.dumps(options), encoding='utf-8')
                run('build', directory)
            except (ValueError, subprocess.TimeoutExpired) as exc:
                message = str(exc) if isinstance(exc, ValueError) else 'PDF processing exceeded five minutes.'
                return screen(book, job, error=message), 400
            finally:
                PROCESS_LOCK.release()
            return redirect(url_for('.review', job=job), code=303)
        result_path = directory / 'result.json'
        result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else None
        return screen(book, job, result=result)

    @bp.post('/<job>/save')
    def save(job):
        directory = folder(job)
        title, listing = request.form.get('title', '').strip(), request.form.get('listing', '').strip()
        if not title or len(title) > 300 or not listing or len(listing) > 30000:
            abort(400, 'Enter a title and description within the displayed limits.')
        if not PROCESS_LOCK.acquire(blocking=False):
            abort(409, 'Another offline PDF is being processed. Try again shortly.')
        try:
            path = directory / 'result.json'
            if not path.exists():
                abort(400, 'Create a preview first.')
            result = json.loads(path.read_text(encoding='utf-8'))
            result.update(title=title, listing=listing)
            (directory / 'title.txt').write_text(title, encoding='utf-8')
            (directory / 'listing.txt').write_text(listing, encoding='utf-8')
            path.write_text(json.dumps(result), encoding='utf-8')
        finally:
            PROCESS_LOCK.release()
        return redirect(url_for('.review', job=job), code=303)

    @bp.get('/<job>/download/<kind>')
    def download(job, kind):
        names = {'preview': 'preview.pdf', 'title': 'title.txt', 'listing': 'listing.txt'}
        if kind not in names:
            abort(404)
        path = folder(job) / names[kind]
        if not path.is_file():
            abort(404)
        return send_file(path, as_attachment=True, download_name=names[kind], max_age=0)

    return bp


def register(app, storage, library_dir=None):
    if not app.secret_key:
        app.secret_key = secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    app.register_blueprint(create_blueprint(storage, library_dir))
