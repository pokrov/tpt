"""Local draft and quality dashboard; no TPT publishing or provider access."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, jsonify, render_template, request, send_file

from core.paths import DATA_DIR, OUTPUT_DIR
from core.workbook_v2 import draft
from core.workbook_v2_pdf import build_pdf
from core.workbook_v2_store import list_drafts, load_draft, save_draft, set_review

bp=Blueprint('workbook_v2',__name__,url_prefix='/v2/plants')


@bp.before_request
def protect():
    if request.host.split(':')[0].lower() not in {'localhost','127.0.0.1'}:abort(403)
    expected=os.environ.get('WEBHOOK_API_KEY','')
    supplied=request.headers.get('X-API-Key','')
    if request.authorization and request.authorization.type=='basic':
        supplied=request.authorization.password or ''
    if expected and not hmac.compare_digest(supplied,expected):
        return 'Use the local generation access key as the password.',401,{'WWW-Authenticate':'Basic realm="V2 workbook review"'}
    if request.method=='POST' and request.headers.get('Origin','').rstrip('/')!=request.host_url.rstrip('/'):
        abort(403)


@bp.after_request
def private(response):
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@bp.get('/')
def index():
    return render_template('workbook_v2.html',drafts=list_drafts())


@bp.post('/draft')
def create_draft():
    """Create one deterministic editorial draft; no live AI request is made."""
    from core.book_library import register_book
    from local_server import GENERATION_LOCK
    if not GENERATION_LOCK.acquire(blocking=False):return jsonify(error='Generation is busy.'),409
    try:
        book=draft()
        stem=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'-plant-v2-draft'
        color=OUTPUT_DIR/(stem+'.pdf')
        ink_dir=DATA_DIR/'v2-ink';ink_dir.mkdir(parents=True,exist_ok=True)
        ink=ink_dir/(stem+'-ink.pdf')
        build_pdf(book,color,page_size='letter',print_mode='color')
        build_pdf(book,ink,page_size='letter',print_mode='ink')
        record=save_draft(book,color,ink_pdf=ink)
        register_book(dict(title=book['title']+' — V2 Draft',theme='Plant growth and observation',
                           grade_band=book['grade_band'],generated_on=datetime.now(timezone.utc).date().isoformat(),
                           resource_type='activity_pack',book_type='plant_reading_observation_v2'),color.name,'V2 offline draft')
        return jsonify(status=record['status'],draft_id=stem,review_url='/v2/plants/'+stem),201
    finally:GENERATION_LOCK.release()


@bp.get('/<draft_id>')
def detail(draft_id):
    try:book,record=load_draft(draft_id)
    except (ValueError,OSError,KeyError):abort(404)
    return render_template('workbook_v2_detail.html',book=book,record=record,draft_id=draft_id)


@bp.get('/<draft_id>/ink')
def ink_file(draft_id):
    try:_,record=load_draft(draft_id)
    except (ValueError,OSError,KeyError):abort(404)
    ink=DATA_DIR/'v2-ink'/record['ink_filename']
    if not ink.is_file():abort(404)
    from core.workbook_v2_store import _hash
    if _hash(ink)!=record['ink_sha256']:abort(409)
    return send_file(ink,as_attachment=True,download_name=ink.name,mimetype='application/pdf')


@bp.post('/<draft_id>/review')
def review(draft_id):
    if not request.is_json:return jsonify(error='Send a JSON review object.'),415
    try:return jsonify(set_review(draft_id,request.get_json(silent=True)))
    except (ValueError,OSError,KeyError) as exc:return jsonify(error=str(exc)),400
