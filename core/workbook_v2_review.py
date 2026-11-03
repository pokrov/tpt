"""Bounded, injectable semantic reviewers. Results never grant human approval."""
from __future__ import annotations

from copy import deepcopy
import json

from core.workbook_v2 import digest, validate


def science_review(book, ask):
    """One optional Gemini completion over the three passages; human sources remain required."""
    book=validate(book)
    payload=[{'reading_id':r['id'],'paragraphs':r['paragraphs']} for r in book['readings']]
    prompt=('Review scientific claims in these grade 3–4 plant passages. Flag false, overbroad, '
            'contradictory or misleading statements, especially seed germination, photosynthesis, '
            'water transport and flowering/non-flowering classification. Do not assume passage '
            'accuracy. Return findings with reading_id, exact_quote, severity (critical/major/minor), '
            'reason, and suggested correction. Return an empty findings array only if none are found. '
            'Do not invent citations or certify rights.\n'+json.dumps(payload,ensure_ascii=False))
    def check(raw):
        findings=raw.get('findings') if isinstance(raw,dict) else None
        if not isinstance(findings,list) or len(findings)>30:raise ValueError('Science review needs at most 30 findings.')
        sources={r['id']:' '.join(r['paragraphs']) for r in book['readings']}
        for item in findings:
            if (not isinstance(item,dict) or item.get('reading_id') not in sources
                    or not isinstance(item.get('exact_quote'),str) or item['exact_quote'] not in sources[item['reading_id']]
                    or item.get('severity') not in {'critical','major','minor'}
                    or any(not isinstance(item.get(k),str) or not item[k].strip() for k in ('reason','suggested_correction'))):
                raise ValueError('Science review finding needs a literal passage quote and complete fields.')
        return findings
    findings=ask(prompt,check,'V2 plant science review',2200)
    return {'status':'Validation failed' if findings else 'Ready for human review',
            'source_hash':digest(payload),'findings':findings,'human_verified':False}


def blind_answer_review(book, ask):
    """Resolve without proposed answers or key; every question ID must be reported."""
    book=validate(book)
    payload=[]
    for reading in book['readings']:
        payload.append({'reading_id':reading['id'],'paragraphs':reading['paragraphs'],
                        'questions':[{'id':q['id'],'kind':q['kind'],'prompt':q['prompt'],
                                      **({'options':q['options']} if q['kind']=='mcq' else {})}
                                     for q in reading['questions']]})
    prompt=('Solve every question independently from the passage. Do not infer an answer from an '
            'unseen key. For MCQs return A/B/C/D, NONE or AMBIGUOUS; for written questions return '
            'a concise supported response. Report question_id, answer, supported, reason and '
            'literal evidence_quote. Flag false scientific premises.\n'+json.dumps(payload,ensure_ascii=False))
    def check(raw):
        reports=raw.get('reports') if isinstance(raw,dict) else None
        expected={q['id']:(r,q) for r in book['readings'] for q in r['questions']}
        if not isinstance(reports,list) or len(reports)!=len(expected):raise ValueError('Review every V2 question once.')
        seen=set()
        for item in reports:
            if not isinstance(item,dict) or item.get('question_id') not in expected or item['question_id'] in seen:
                raise ValueError('Unknown or duplicate question ID in blind review.')
            seen.add(item['question_id'])
            reading,q=expected[item['question_id']]
            if (not isinstance(item.get('evidence_quote'),str) or item['evidence_quote'] not in ' '.join(reading['paragraphs'])
                    or type(item.get('supported')) is not bool or not isinstance(item.get('reason'),str) or not item['reason'].strip()):
                raise ValueError('Blind review needs literal source evidence and explicit verdict.')
            if q['kind']=='mcq' and item.get('answer') not in {'A','B','C','D','NONE','AMBIGUOUS'}:
                raise ValueError('Invalid blind MCQ answer.')
            if q['kind']=='short' and not isinstance(item.get('answer'),str):
                raise ValueError('Invalid blind written answer.')
        return reports
    reports=ask(prompt,check,'V2 blind answer review',2600)
    expected={q['id']:q for r in book['readings'] for q in r['questions']}
    issues=[]
    for item in reports:
        q=expected[item['question_id']]
        if not item['supported'] or (q['kind']=='mcq' and item['answer']!=q['answer']):
            issues.append({'question_id':item['question_id'],'reason':item['reason']})
    return {'status':'Validation failed' if issues else 'Ready for human review',
            'canonical_hash':digest(book),'issues':issues,'reports':reports,'human_verified':False}
