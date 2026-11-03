"""Hash-bound V2 draft records and explicit human review transitions."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from core.paths import BASE_DIR, DATA_DIR
from core.workbook_v2 import digest, review_issues, validate

ROOT=DATA_DIR/'v2-drafts'


def _hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def _write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,suffix='.part',delete=False) as f:
        json.dump(value,f,indent=2,ensure_ascii=False);temp=Path(f.name)
    try:os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def save_draft(book, pdf, *, ink_pdf=None, root=ROOT):
    book=validate(book);pdf=Path(pdf)
    name=pdf.stem
    folder=Path(root)/name
    if folder.exists():raise ValueError('Draft record already exists; do not overwrite a reviewed workbook.')
    now=datetime.now(timezone.utc).isoformat()
    sources={reading['id']:reading['source_hash'] for reading in book['readings']}
    logo=BASE_DIR/'assets'/'store-logo.png'
    font_path=next((Path(p) for p in (os.getenv('V2_FONT_PATH',''),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if p and Path(p).is_file()),None)
    diagram_code=BASE_DIR/'core'/'workbook_v2_pdf.py'
    assets=[dict(id='cover-logo',type='logo',filename='assets/store-logo.png',sha256=_hash(logo) if logo.is_file() else '',source='user supplied',
                 method='supplied bitmap',created_on='',model='',terms_reference='',attribution='',
                 commercial_status='Unverified',reviewer_notes='Ownership and TPT rights require evidence.'),
            dict(id='science-diagrams',type='diagram',filename='core/workbook_v2_pdf.py',sha256=_hash(diagram_code),source='locally authored code',
                 method='deterministic vector drawing',created_on=now,model='',terms_reference='',attribution='',
                 commercial_status='Unverified',reviewer_notes='Review accuracy and commercial rights.'),
            dict(id='body-font',type='font',filename=str(font_path) if font_path else 'PDF built-in Helvetica',sha256=_hash(font_path) if font_path else '',source='local renderer',
                 method='bundled font',created_on='',model='',terms_reference='',attribution='',
                 commercial_status='Unverified',reviewer_notes='Confirm exact font and commercial embedding terms.')]
    for reading in book['readings']:
        assets.append(dict(id='text-'+reading['id'],type='passage',filename='',sha256=reading['source_hash'],source='offline editorial draft',
                           method='canonical fixture',created_on=now,model='',terms_reference='',attribution='',
                           commercial_status='Unverified',reviewer_notes='Check originality and source support.'))
    science_claims=[dict(id=f'{reading["id"]}-p{n}',reading_id=reading['id'],text=paragraph,
                         status='Unverified',source_url='',reviewer_notes='')
                    for reading in book['readings'] for n,paragraph in enumerate(reading['paragraphs'],1)]
    record=dict(schema_version=2,ledger_version=1,profile=book['profile'],title=book['title'],grade_band=book['grade_band'],
                created_at=now,status='Draft',pdf_filename=pdf.name,pdf_sha256=_hash(pdf),
                ink_filename=Path(ink_pdf).name if ink_pdf else None,ink_sha256=_hash(ink_pdf) if ink_pdf else None,
                canonical_hash=digest(book),source_hashes=sources,science_status='Unverified',
                rights_status='Unverified',quality_score=None,scores=None,
                issues=review_issues(book)+['Final question and answer key need human verification.',
                                            'Final PDF layout needs human verification.'],
                assets=assets,science_claims=science_claims,answer_review='Validation required',
                layout_review='Validation required',history=[])
    _write(folder/'book.json',book)
    _write(folder/'review.json',record)
    return record


def load_draft(name, *, root=ROOT):
    if not name or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for ch in name):
        raise ValueError('Invalid draft ID.')
    folder=Path(root)/name
    book=json.loads((folder/'book.json').read_text(encoding='utf-8'))
    record=json.loads((folder/'review.json').read_text(encoding='utf-8'))
    validate(book)
    if record.get('canonical_hash')!=digest(book):raise ValueError('Canonical draft changed after review.')
    from core.paths import OUTPUT_DIR
    pdf=OUTPUT_DIR/record['pdf_filename']
    if not pdf.is_file() or _hash(pdf)!=record['pdf_sha256']:raise ValueError('Draft PDF changed after review.')
    return book,record


def list_drafts(*, root=ROOT):
    if not Path(root).exists():return []
    records=[]
    for folder in sorted(Path(root).iterdir(),reverse=True):
        if folder.is_dir() and (folder/'review.json').is_file():
            try:records.append(json.loads((folder/'review.json').read_text(encoding='utf-8')))
            except (ValueError,OSError):continue
    return records


def set_review(name, changes, *, root=ROOT):
    """Only human-supplied evidence can clear separate science/rights/answer/layout gates."""
    book,record=load_draft(name,root=root)
    allowed={'science_status','rights_status','answer_review','layout_review','status','reviewer_notes','scores','assets','science_claims'}
    if not isinstance(changes,dict) or set(changes)-allowed:raise ValueError('Unsupported review field.')
    for key in ('science_status','rights_status','answer_review','layout_review'):
        if key in changes and changes[key] not in {'Unverified','Validation required','Validation failed','Human verified'}:
            raise ValueError(f'Invalid {key}.')
    if 'scores' in changes:
        weights={'science':25,'education':25,'answers':20,'layout':15,'originality_rights':15}
        if not isinstance(changes['scores'],dict) or set(changes['scores'])!=set(weights):
            raise ValueError('Provide all five weighted quality scores.')
        if any(type(changes['scores'][key]) is not int or not 0<=changes['scores'][key]<=maximum
               for key,maximum in weights.items()):
            raise ValueError('Quality category score exceeds its weight.')
    if 'reviewer_notes' in changes and (not isinstance(changes['reviewer_notes'],str) or len(changes['reviewer_notes'])>4000):
        raise ValueError('Reviewer notes must be text of at most 4000 characters.')
    if 'assets' in changes:
        assets=changes['assets']
        if (not isinstance(assets,list) or len(assets)!=len(record['assets'])
                or [a.get('id') for a in assets if isinstance(a,dict)]!=[a['id'] for a in record['assets']]):
            raise ValueError('The complete original asset inventory and order must be retained.')
        for old,asset in zip(record['assets'],assets):
            if any(asset.get(k)!=old.get(k) for k in ('id','type','filename','sha256','source','method','created_on','model')):
                raise ValueError('Asset identity and origin cannot be replaced in review.')
            if asset.get('commercial_status') not in {'Unverified','Verified'}:
                raise ValueError('Invalid asset rights status.')
            if asset['commercial_status']=='Verified' and (not asset.get('terms_reference') or not asset.get('reviewer_notes')):
                raise ValueError('Verified assets need terms or permission evidence and reviewer notes.')
    if 'science_claims' in changes:
        claims=changes['science_claims']
        if (not isinstance(claims,list) or len(claims)!=len(record['science_claims'])
                or not all(isinstance(c,dict) for c in claims)
                or [(c.get('id'),c.get('reading_id'),c.get('text')) for c in claims]
                   !=[(c['id'],c['reading_id'],c['text']) for c in record['science_claims']]):
            raise ValueError('Retain every original science review unit and its exact passage wording.')
        ids=set()
        for claim in claims:
            if (not isinstance(claim,dict) or not isinstance(claim.get('id'),str)
                    or not claim['id'].strip() or len(claim['id'])>80 or claim['id'] in ids
                    or claim.get('reading_id') not in {r['id'] for r in book['readings']}):
                raise ValueError('Each science claim needs a unique ID and current reading ID.')
            ids.add(claim['id'])
            if (claim.get('status') not in {'Unverified','Verified','Rejected'} or not isinstance(claim.get('text'),str)
                    or not isinstance(claim.get('source_url'),str) or not isinstance(claim.get('reviewer_notes'),str)):
                raise ValueError('Invalid science claim fields.')
            if claim['status']=='Verified' and (not claim['source_url'].startswith('https://') or not claim['reviewer_notes'].strip()):
                raise ValueError('Verified science claims need a source URL and human review notes.')
    if 'status' in changes and changes['status'] not in {'Draft','Validation required','Validation failed','Ready for human review','Human approved','Rejected'}:
        raise ValueError('Invalid status.')
    updated={**record,**changes}
    if 'scores' in changes:updated['quality_score']=sum(changes['scores'].values())
    issues=[]
    if updated.get('science_status')!='Human verified':issues.append('Scientific claims need independent human source review.')
    issues += [f"{a['id']} commercial rights are Unverified." for a in updated['assets'] if a.get('commercial_status')!='Verified']
    if updated.get('answer_review')!='Human verified':issues.append('Final question and answer key need human verification.')
    if updated.get('layout_review')!='Human verified':issues.append('Final PDF layout needs human verification.')
    updated['issues']=issues
    if updated.get('rights_status')=='Human verified' and any(a.get('commercial_status')!='Verified' for a in updated['assets']):
        raise ValueError('Rights cannot be verified while an asset is Unverified.')
    if updated.get('science_status')=='Human verified':
        if any(c.get('status')!='Verified' for c in updated['science_claims']):
            raise ValueError('Every passage review unit needs verification with no unresolved claim.')
    if updated['status']=='Human approved':
        gates=('science_status','rights_status','answer_review','layout_review')
        if any(updated.get(key)!='Human verified' for key in gates):
            raise ValueError('Science, rights, answers and layout each need human verification.')
        if any(asset.get('commercial_status')!='Verified' for asset in updated['assets']):
            raise ValueError('Every asset needs verified commercial rights evidence.')
        if not updated.get('science_claims'):
            raise ValueError('No source-backed science claim review is recorded.')
        if not isinstance(updated.get('reviewer_notes'),str) or not updated['reviewer_notes'].strip():
            raise ValueError('Human approval needs a reviewer note documenting the decision.')
    updated['history']=record['history']+[dict(at=datetime.now(timezone.utc).isoformat(),status=updated['status'],
                                              note=changes.get('reviewer_notes',''))]
    _write(Path(root)/name/'review.json',updated)
    return updated
