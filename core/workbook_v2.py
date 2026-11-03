"""Versioned, source-bound plant workbook drafts; no provider calls or approval side effects."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

SCHEMA_VERSION = 2
PROFILE = 'plant_reading_observation_v2'
FORBIDDEN = (
    r'all non[- ]flowering plants (?:make|produce|use) spores',
    r'sunlight (?:is|becomes) (?:plant )?food',
    r'soil (?:makes|supplies|provides) (?:the )?plant(?:s)?[\x27’]?(?:s)? food',
    r'(?:xylem|straws?) (?:push|defy gravity)',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def draft():
    """An editable offline editorial seed; science and rights remain unverified."""
    readings = [
        dict(id='seed', title='From Seed to Seedling', objective='Describe what a bean seed needs to start growing.',
             paragraphs=[
                 'A dry bean seed holds a young plant and stored food inside its seed coat. The coat protects the parts inside, although it cannot protect a seed from every danger. A seed begins to germinate when it takes in water under suitable conditions. It also needs air and a suitable temperature. A seed does not have to wait for spring rain if someone provides those conditions indoors.',
                 'As the bean takes in water, it swells. The first root grows downward and absorbs water. A shoot then grows upward. The young plant uses food stored in the seed while its first leaves develop. Later, green leaves can make sugars using light energy. This change from seed to seedling takes time, and different seeds may grow at different rates.'
             ], vocabulary={'germination':'the beginning of growth from a seed', 'seedling':'a young plant'},
             questions=[
                 dict(id='seed-m1', kind='mcq', prompt='What does a bean seed need to begin germinating?', options={'A':'Water, air, and a suitable temperature','B':'A flower, a fruit, and a cone','C':'Only soil and direct sunlight','D':'Only cold weather and rain'}, answer='A', evidence='It also needs air and a suitable temperature.'),
                 dict(id='seed-m2', kind='mcq', prompt='Which part grows first after the seed swells?', options={'A':'A flower','B':'A fruit','C':'A root','D':'A leaf'}, answer='C', evidence='The first root grows downward and absorbs water.'),
                 dict(id='seed-s1', kind='short', prompt='Which sentence shows that roots appear before shoots? Copy it and explain the order.', answer='The first root grows downward and absorbs water. A shoot then grows upward.', evidence='The first root grows downward and absorbs water. A shoot then grows upward.', rubric='Accept a correct quotation or paraphrase naming root before shoot.')]),
        dict(id='leaves', title='How Green Leaves Make Sugars', objective='Identify the inputs and products of photosynthesis.',
             paragraphs=[
                 'A green leaf needs light to make sugars. Its roots take in water, and its leaves take in carbon dioxide from the air. Carbon dioxide is a gas in the air. Using energy from light, the plant changes water and carbon dioxide into sugars. The plant also releases oxygen. This process is called photosynthesis.',
                 'Sunlight gives energy for the process; sunlight is not a food that the plant eats. The sugars are food the plant has made. A young seedling can use food stored in its seed before its leaves make much sugar. A healthy green leaf needs water, carbon dioxide, and light to make sugars. A short dark period does not mean that a plant immediately dies. Leaves can use the sugars as the plant grows.'
             ], vocabulary={'photosynthesis':'the process in which a plant uses light energy to make sugars from water and carbon dioxide', 'carbon dioxide':'a gas in the air'},
             questions=[
                 dict(id='leaves-m1',kind='mcq',prompt='Which two materials does a leaf use to make sugars?',options={'A':'Oxygen and soil','B':'Water and carbon dioxide','C':'Sunlight and sugar','D':'Roots and flowers'},answer='B',evidence='Using energy from light, the plant changes water and carbon dioxide into sugars.'),
                 dict(id='leaves-m2',kind='mcq',prompt='What does sunlight provide for photosynthesis?',options={'A':'Energy','B':'Water','C':'Carbon dioxide','D':'Stored seed food'},answer='A',evidence='Sunlight gives energy for the process; sunlight is not a food that the plant eats.'),
                 dict(id='leaves-s1',kind='short',prompt='Explain why sunlight is not itself plant food. Use a detail from the reading.',answer='Light provides energy; the plant makes sugars from water and carbon dioxide.',evidence='Sunlight gives energy for the process; sunlight is not a food that the plant eats.',rubric='Accept an explanation distinguishing light energy from sugars made by the plant.')]),
        dict(id='transport', title='Water Travels Through a Bean Plant', objective='Trace water from roots through stem to leaves.',
             paragraphs=[
                 'A bean plant growing in soil takes in water through its roots. Tiny root hairs increase the root area that touches water in the soil. Dissolved minerals may enter with the water. The stem supports the plant and contains tissues that carry water toward the leaves. Xylem is the tissue that carries water upward through the plant.',
                 'A straw analogy does not explain how water moves. Water can move through the xylem as water evaporates from leaves and draws more water upward. For this grade, follow the pathway: soil to roots, roots to stem, and stem to leaves. Leaves need water for photosynthesis. If the bean plant cannot get enough water, its leaves may wilt. A wilted plant needs careful observation before anyone decides what caused the change.'
             ], vocabulary={'xylem':'plant tissue that carries water upward', 'dissolved':'mixed into a liquid'},
             questions=[
                 dict(id='transport-m1',kind='mcq',prompt='Where does the bean plant take in water?',options={'A':'Through its roots','B':'Through its flowers','C':'Through dry seeds','D':'Through its fruit'},answer='A',evidence='A bean plant growing in soil takes in water through its roots.'),
                 dict(id='transport-m2',kind='mcq',prompt='What carries water upward through the plant?',options={'A':'Seed coat','B':'Xylem','C':'Sugar','D':'Petals'},answer='B',evidence='Xylem is the tissue that carries water upward through the plant.'),
                 dict(id='transport-s1',kind='short',prompt='Trace the path of water from soil to leaf. Why do leaves need water?',answer='Soil → roots → stem → leaves; leaves need water for photosynthesis.',evidence='For this grade, follow the pathway: soil to roots, roots to stem, and stem to leaves. Leaves need water for photosynthesis.',rubric='Accept the correct ordered path and photosynthesis as the reason.')]),
    ]
    for reading in readings:
        reading['source_hash'] = digest(reading['paragraphs'])
        for question in reading['questions']:
            question['source_hash'] = reading['source_hash']
    return dict(schema_version=SCHEMA_VERSION, profile=PROFILE, title='How Plants Grow', grade_band='3rd-4th',
                readings=readings, objective='Read evidence about bean growth, observe seeds, and explain changes.',
                materials=['2–3 dry beans','clear cup or bag','paper towel or soil','water','ruler marked in centimeters'],
                science_review={'status':'Unverified','claims':[]},
                rights={'images':'Unverified','fonts':'Unverified','logo':'Unverified','text':'Unverified'},
                human_status='Draft')


def validate(book):
    if not isinstance(book,dict) or book.get('schema_version') != SCHEMA_VERSION or book.get('profile') != PROFILE:
        raise ValueError('Unknown V2 workbook schema or profile.')
    if book.get('grade_band') != '3rd-4th' or not isinstance(book.get('readings'),list) or len(book['readings']) != 3:
        raise ValueError('V2 plant edition needs three grade 3–4 readings.')
    ids = set()
    for reading in book['readings']:
        if not isinstance(reading,dict) or not isinstance(reading.get('paragraphs'),list) or not all(isinstance(p,str) for p in reading['paragraphs']):
            raise ValueError('Each V2 reading needs plain-text paragraphs.')
        source = ' '.join(reading['paragraphs'])
        if not 120 <= len(source.split()) <= 180:
            raise ValueError('Each V2 reading needs 120–180 words.')
        if digest(reading['paragraphs']) != reading.get('source_hash'):
            raise ValueError('Passage changed; dependent questions and key need revalidation.')
        if any(re.search(pattern,source,re.I) for pattern in FORBIDDEN):
            raise ValueError('A known misleading plant-science claim needs correction.')
        if not isinstance(reading.get('questions'),list) or len(reading['questions']) != 3:
            raise ValueError('Each reading needs three reviewed questions.')
        for q in reading['questions']:
            if q.get('id') in ids or not q.get('id'):
                raise ValueError('Question IDs must be distinct.')
            ids.add(q['id'])
            if q.get('source_hash') != reading['source_hash'] or not q.get('evidence') or q['evidence'] not in source:
                raise ValueError(f"Question {q['id']} lacks current literal passage evidence.")
            if not isinstance(q.get('answer'),str) or not q['answer'].strip():
                raise ValueError(f"Question {q['id']} lacks an answer.")
            if q.get('kind') == 'mcq':
                options = q.get('options')
                if not isinstance(options,dict) or set(options) != set('ABCD') or q['answer'] not in options or len(set(options.values())) != 4:
                    raise ValueError(f"Question {q['id']} needs four distinct options and one selected answer.")
            elif q.get('kind') != 'short' or not q.get('rubric'):
                raise ValueError(f"Question {q['id']} needs an answer rubric.")
    if book.get('human_status') not in {'Draft','Validation required','Validation failed','Ready for human review','Human approved','Rejected'}:
        raise ValueError('Invalid human review status.')
    if set(book.get('rights',{})) != {'images','fonts','logo','text'}:
        raise ValueError('Incomplete rights categories.')
    return deepcopy(book)


def review_issues(book):
    """A score never clears a blocker; semantic science still needs human review."""
    validate(book)
    issues=[]
    if book['science_review'].get('status') != 'Human verified':
        issues.append('Scientific claims need independent human source review.')
    issues += [f'{name} commercial rights are Unverified.' for name,status in book['rights'].items() if status != 'Verified']
    return issues
