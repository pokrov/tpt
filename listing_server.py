"""Standalone offline app: python listing_server.py (no workbook imports)."""
from pathlib import Path
import os

from flask import Flask, redirect
from listing_tool.web import register


def create_app(storage=None, library_dir=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=81 * 1024 * 1024, TRUSTED_HOSTS=['localhost', '127.0.0.1'])
    root = storage or Path(os.environ.get('LISTING_DATA_DIR', Path(__file__).resolve().parent / 'local-data' / 'listing-previews'))
    library = library_dir or Path(os.environ.get('LISTING_LIBRARY_DIR', Path(__file__).resolve().parent / 'local-data' / 'output'))
    register(app, root, library_dir=library)

    @app.get('/')
    def home():
        return redirect('/listing-tool/')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'offline-listing'}

    return app


if __name__ == '__main__':
    create_app().run(host=os.environ.get('LISTING_BIND', '127.0.0.1'), port=8081, debug=False, use_reloader=False)
