"""Separate, fixed editorial How Plants Grow V2.1 candidate; no provider calls."""
from __future__ import annotations

from copy import deepcopy
import re

from core.workbook_v2 import draft as v2_draft, digest, FORBIDDEN

PROFILE = 'plant_reading_observation_v2_1'


def draft():
    book = v2_draft()
    book.update(schema_version='2.1', profile=PROFILE, human_status='Draft')
    seed, leaves, transport = book['readings']
    seed['paragraphs'][0] = seed['paragraphs'][0].replace(
        'a young plant and stored food', 'an embryo (a young plant) and stored food')
    seed['vocabulary']['embryo'] = 'the young plant inside a seed'
    leaves['paragraphs'][1] = leaves['paragraphs'][1].replace(
        'Leaves can use the sugars as the plant grows.',
        'Plants use the sugars they make for energy and to build new parts as they grow.')
    extra = [
        dict(id='seed-seq', kind='sequence', prompt='Put these events in order by writing 1–3: shoot grows; seed takes in water; first root grows.',
             items=['Shoot grows', 'Seed takes in water', 'First root grows'], answer=[3, 1, 2],
             evidence='As the bean takes in water, it swells. The first root grows downward and absorbs water. A shoot then grows upward.',
             rubric='1 seed takes in water; 2 first root grows; 3 shoot grows.'),
        dict(id='leaves-class', kind='classify', prompt='Classify each: water, carbon dioxide, light energy, sugars, oxygen. Label material input, energy input, or output.',
             items=['Water', 'Carbon dioxide', 'Light energy', 'Sugars', 'Oxygen'],
             answer=['Material input', 'Material input', 'Energy input', 'Output', 'Output'],
             evidence='Using energy from light, the plant changes water and carbon dioxide into sugars. The plant also releases oxygen.',
             rubric='Light supplies energy; it is not a material consumed to make sugar.'),
        dict(id='transport-order', kind='sequence', prompt='Put the water pathway in order by writing 1–4: leaves; soil; stem; roots.',
             items=['Leaves', 'Soil', 'Stem', 'Roots'], answer=[4, 1, 3, 2],
             evidence='For this grade, follow the pathway: soil to roots, roots to stem, and stem to leaves.',
             rubric='1 soil; 2 roots; 3 stem; 4 leaves.'),
    ]
    for reading, question in zip(book['readings'], extra):
        reading['source_hash'] = digest(reading['paragraphs'])
        for q in reading['questions']:
            q['source_hash'] = reading['source_hash']
        question['source_hash'] = reading['source_hash']
        reading['questions'].insert(2, question)
    return validate(book)


def validate(book):
    if (not isinstance(book, dict) or book.get('schema_version') != '2.1'
            or book.get('profile') != PROFILE or book.get('grade_band') != '3rd-4th'
            or not isinstance(book.get('readings'), list) or len(book['readings']) != 3):
        raise ValueError('Invalid V2.1 profile or reading inventory.')
    ids = set()
    for reading in book['readings']:
        source = ' '.join(reading['paragraphs'])
        if not 120 <= len(source.split()) <= 180 or any(re.search(p, source, re.I) for p in FORBIDDEN):
            raise ValueError('V2.1 passage length or known science claim is invalid.')
        if digest(reading['paragraphs']) != reading.get('source_hash'):
            raise ValueError('Passage changed; questions and key require revalidation.')
        qs = reading.get('questions')
        if not isinstance(qs, list) or len(qs) != 4 or [q.get('kind') for q in qs] != ['mcq', 'mcq', 'sequence' if reading['id'] != 'leaves' else 'classify', 'short']:
            raise ValueError('Every reading needs two MCQs, one structured task and one written response.')
        for q in qs:
            qid = q.get('id')
            if not isinstance(qid, str) or not qid or qid in ids:
                raise ValueError('Question IDs must be unique.')
            ids.add(qid)
            if q.get('source_hash') != reading['source_hash'] or not isinstance(q.get('evidence'), str) or q['evidence'] not in source:
                raise ValueError(f'{qid}: current literal passage evidence required.')
            if not isinstance(q.get('prompt'), str) or not q['prompt'].strip() or not isinstance(q.get('rubric', '') if q['kind'] != 'mcq' else '', str):
                raise ValueError(f'{qid}: prompt or scoring guidance invalid.')
            if q['kind'] == 'mcq':
                options = q.get('options')
                if not isinstance(options, dict) or set(options) != set('ABCD') or len(set(options.values())) != 4 or q.get('answer') not in options:
                    raise ValueError(f'{qid}: ambiguous or incomplete MCQ.')
            elif q['kind'] in {'sequence', 'classify'}:
                items, answer = q.get('items'), q.get('answer')
                if not isinstance(items, list) or not isinstance(answer, list) or len(items) != len(answer) or not 3 <= len(items) <= 5 or not q.get('rubric'):
                    raise ValueError(f'{qid}: structured task and key disagree.')
                if q['kind'] == 'sequence' and sorted(answer) != list(range(1, len(items) + 1)):
                    raise ValueError(f'{qid}: sequence key is not a permutation.')
                if q['kind'] == 'classify' and any(a not in {'Material input', 'Energy input', 'Output'} for a in answer):
                    raise ValueError(f'{qid}: invalid classification label.')
            elif q['kind'] == 'short' and (not isinstance(q.get('answer'), str) or not q.get('rubric')):
                raise ValueError(f'{qid}: written key needs an answer and rubric.')
    if book.get('human_status') != 'Draft' or any(v != 'Unverified' for v in book.get('rights', {}).values()):
        raise ValueError('V2.1 must remain a draft with unverified rights.')
    return deepcopy(book)
