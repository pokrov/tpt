"""PDF-bound product facts from final workbook data; no providers or answer text."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile

from pypdf import PdfReader

SKILLS = {'main_idea':'Identifying the main idea', 'detail':'Finding explicit details',
          'inference':'Making text-based inferences', 'vocabulary':'Understanding vocabulary in context',
          'cause_effect':'Explaining cause and effect', 'text_structure':'Recognizing text structure',
          'author_purpose':"Identifying the author's purpose", 'comparison':'Comparing written information'}


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def info_path(pdf):
    return Path(pdf).with_suffix('.product.json')


def plain(value):
    return value.strip() if isinstance(value, str) else ''


def build_product_info(story, pdf, sheet_counts):
    """Read only final canonical fields, never model-generated marketing prose."""
    reader = PdfReader(str(pdf))
    total = len(reader.pages)
    if len(sheet_counts) != len(story['pages']) or total != 2 + sum(sheet_counts):
        raise ValueError('Product information does not match the final physical page count.')
    units = story.get('reading_units', [])
    records = [dict(number=1, heading=story['title'], role='cover', text='', reading=False,
                    mcq=0, question_count=0, continuation=False, summary='')]
    refs = []
    for page, count in zip(story['pages'], sheet_counts):
        role = page.get('page_type')
        unit_number = page.get('reading_unit')
        unit = units[unit_number-1] if type(unit_number) is int and 1 <= unit_number <= len(units) else {}
        exercise = page.get('exercise', {})
        questions = unit.get('questions', []) if role == 'qcm' else exercise.get('questions', [])
        paragraphs = unit.get('paragraphs', []) if role == 'reading' else []
        sources = [plain(exercise.get('passage'))]
        for field in ('stimuli','captions'):
            sources += [plain(s.get('text')) for s in exercise.get(field, []) if isinstance(s,dict)]
        source = '\n'.join(p for p in paragraphs + sources if isinstance(p,str) and p.strip())
        text = '\n'.join([source, plain(exercise.get('directions'))] + [plain(q.get('prompt')) for q in questions])
        title = plain(unit.get('title')) or plain(page.get('title')) or f'Activity {len(records)}'
        summary = re.split(r'(?<=[.!?])\s+', ' '.join(source.split()))[0] if source else ''
        if len(summary) > 400:
            summary = ''
        number = len(records)+1
        for index, question in enumerate(questions, 1):
            if question.get('skill') in SKILLS:
                refs.append(dict(skill=question['skill'], page=number, question=index))
        for continuation in range(count):
            records.append(dict(number=len(records)+1, heading=title, role='student', text=text,
                reading=role == 'reading' and not continuation,
                mcq=len(questions) if role == 'qcm' and not continuation else 0,
                question_count=len(questions) if not continuation else 0,
                continuation=bool(continuation), summary=summary if not continuation else '',
                task_prompts=[plain(q.get('prompt')) for q in questions] if not continuation else [],
                task_directions=plain(exercise.get('directions')) if not continuation else ''))
    records.append(dict(number=total, heading='Answer Key', role='answer key / teacher page',
                        text='', reading=False, mcq=0, question_count=0, continuation=False, summary=''))
    grade = {'3rd-4th':'3-4','5th-6th':'5-6'}.get(story['grade_band'], '')
    return dict(schema_version=1, filename=Path(pdf).name, pdf_sha256=file_hash(pdf),
                topic=story['title'], grade=grade, book_type=story.get('book_type','reading_qcm'),
                total=total, pages=records, skill_refs=refs,
                content_reviewed=story.get('content_checks',{}).get('status') == 'passed')


def write_product_info(story, pdf, sheet_counts):
    data = build_product_info(story, pdf, sheet_counts)
    target = info_path(pdf)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.part', mode='w', encoding='utf-8', delete=False) as handle:
        staged = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
    try:
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    return target


def read_product_info(pdf, metadata=None):
    """Validate file binding, coverage and question references before bypassing OCR."""
    metadata = Path(metadata) if metadata else info_path(pdf)
    if metadata.is_symlink() or metadata.stat().st_size > 2*1024*1024:
        raise ValueError('Invalid product information file.')
    data = json.loads(metadata.read_text(encoding='utf-8'))
    if not isinstance(data,dict):
        raise ValueError('Invalid product information object.')
    reader = PdfReader(str(pdf))
    total = len(reader.pages)
    if (type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not 3 <= total <= 100
            or type(data.get('total')) is not int
            or data.get('pdf_sha256') != file_hash(pdf) or data.get('total') != total
            or data.get('grade') not in {'3-4','5-6'}
            or not isinstance(data.get('topic'),str) or not 1 <= len(data['topic']) <= 180
            or not isinstance(data.get('pages'),list) or len(data['pages']) != total):
        raise ValueError('Saved product information does not match this PDF.')
    pages = []
    for number, (record, page) in enumerate(zip(data['pages'],reader.pages),1):
        if (not isinstance(record,dict) or type(record.get('number')) is not int or record['number'] != number
                or record.get('role') not in {'cover','student','answer key / teacher page'}
                or not isinstance(record.get('heading'),str) or not 1 <= len(record['heading']) <= 200
                or not isinstance(record.get('text'),str) or len(record['text']) > 100000
                or not isinstance(record.get('summary'),str) or len(record['summary']) > 400
                or type(record.get('reading')) is not bool or type(record.get('continuation')) is not bool
                or type(record.get('mcq')) is not int or type(record.get('question_count')) is not int
                or not 0 <= record['mcq'] <= record['question_count'] <= 100):
            raise ValueError('Invalid saved page facts.')
        if 'task_prompts' in record and (not isinstance(record['task_prompts'],list)
                or len(record['task_prompts']) != record['question_count']
                or any(not isinstance(text,str) or len(text)>6000 for text in record['task_prompts'])):
            raise ValueError('Invalid saved task prompts.')
        if 'task_directions' in record and (not isinstance(record['task_directions'],str) or len(record['task_directions'])>6000):
            raise ValueError('Invalid saved task directions.')
        pages.append({**record, 'width':round(float(page.mediabox.width),2),
                      'height':round(float(page.mediabox.height),2), 'text_method':'agent', 'ocr_confidence':None})
    if pages[0]['role'] != 'cover' or pages[-1]['role'] != 'answer key / teacher page' or any(p['role'] != 'student' for p in pages[1:-1]):
        raise ValueError('Invalid saved cover/student/key structure.')
    refs = data.get('skill_refs')
    if not isinstance(refs,list) or len(refs) > 1000:
        raise ValueError('Invalid saved skill references.')
    for ref in refs:
        if (not isinstance(ref,dict) or ref.get('skill') not in SKILLS
                or type(ref.get('page')) is not int or not 1 < ref['page'] < total
                or type(ref.get('question')) is not int
                or not 1 <= ref['question'] <= pages[ref['page']-1]['question_count']):
            raise ValueError('Invalid saved skill reference.')
    return dict(pages=pages, total=total, topic=data['topic'], grade=data['grade'],
                suggested=[p['number'] for p in pages if p['role']=='student'][:3],
                ocr_pages=[], metadata_source='agent', skill_refs=refs,
                content_reviewed=data.get('content_reviewed') is True)
