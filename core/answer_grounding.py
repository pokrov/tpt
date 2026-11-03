"""Require explicit coverage and real printed evidence for answer-key claims."""
import re
import unicodedata


def normalized(text):
    text = unicodedata.normalize('NFKC', text)
    text = text.translate(str.maketrans({'’':"'", '‘':"'", '“':'"', '”':'"', '–':'-', '—':'-'}))
    return ' '.join(text.split()).casefold()


def source_records(page):
    exercise = page.get('exercise', {})
    records = {}
    if isinstance(exercise.get('passage'), str) and exercise['passage'].strip():
        records['passage'] = exercise['passage']
    for field, prefix in (('stimuli','stimulus_'), ('captions','caption_')):
        for record in exercise.get(field, []) or []:
            if isinstance(record, dict) and isinstance(record.get('id'), str) and isinstance(record.get('text'), str):
                records[prefix+record['id']] = record['text']
    return records


def evidence_bank(page):
    """Number bounded, literal excerpts locally, including printed question givens.

    IDs are page-local and regenerated from canonical text during validation.
    Never recover a missing ID by guessing a source or matching an answer.
    """
    records = source_records(page)
    for question in page.get('exercise', {}).get('questions', []):
        records['question_'+question['id']] = question['prompt']
    bank = []
    for slot, text in records.items():
        remaining = text.strip()
        while remaining:
            end = len(remaining)
            if end > 300:
                # Prefer a complete sentence, then a word boundary. No ellipses,
                # paraphrases or invented text enter the canonical excerpt bank.
                boundaries = list(re.finditer(r'[.!?](?=\s)|\n', remaining[:301]))
                end = boundaries[-1].end() if boundaries and boundaries[-1].end() >= 150 else remaining.rfind(' ', 0, 301)
                if end <= 0 or end > 300:
                    end = 300
            excerpt = remaining[:end].strip()
            if excerpt:
                bank.append({'id':f'E{len(bank)+1}', 'slot':slot, 'text':excerpt})
            remaining = remaining[end:].lstrip()
    return bank


def answer_unit_bank(answer):
    """Number complete canonical answer units locally; never ask a reviewer to copy them.

    Split at sentence/semicolon boundaries, retain short labels with their text,
    and merge an oversized tail. Printed answers are never changed. Decimal
    points and common abbreviations do not create spurious units.
    """
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('Answer review needs a nonempty canonical answer')
    from core.matching_grounding import matching_answer_units
    matching=matching_answer_units(answer)
    if matching:
        return [{'id':index,'text':text} for index,text in enumerate(matching,1)]
    fragments=[]; start=0
    abbreviation=re.compile(r'(?:\b(?:Dr|Mr|Mrs|Ms|St|Jr|Sr|vs|etc)|\b(?:U\.S|U\.K|e\.g|i\.e|a\.m|p\.m))\.$',re.I)
    for match in re.finditer(r'[.!?;]\s+|\n+',answer):
        end=match.start()+1 if answer[match.start()] in '.!?;' else match.start()
        fragment=answer[start:end].strip()
        if abbreviation.search(fragment) or re.fullmatch(r'(?:\d+|[A-Z])\.',fragment):
            continue
        if fragment:fragments.append(fragment)
        start=match.end()
    tail=answer[start:].strip()
    if tail:fragments.append(tail)
    units=[]; pending=''
    for fragment in fragments:
        text=(pending+' '+fragment).strip(); pending=''
        if len(re.findall(r'\w+',text))<3:
            pending=text
        else:
            units.append(text)
    if pending:
        if units:units[-1]+=' '+pending
        else:units.append(pending)
    if len(units)>6:units=units[:5]+[' '.join(units[5:])]
    return [{'id':index,'text':text} for index,text in enumerate(units,1)]


def claim_schema():
    from core.response_schemas import obj, array, text
    from core.review_format import CLAIM_REASON_LIMIT
    evidence = obj({'evidence_id':text(12,'Exact ID from this activity\'s evidence_bank. Select excerpts proving every assertion; do not reconstruct a quote or source ID.')})
    return array(obj({'claim_id':{'type':'integer','description':'ID from this question\'s supplied answer_units. Review every assertion in that complete unit; no copied answer text is required.'},
                      'supported':{'type':'boolean'}, 'evidence':array(evidence,0,4),
                      'reason':text(CLAIM_REASON_LIMIT,'Explain support or identify invented details. No outside facts or image guesses.')}),1,6)


def claim_issues(check, question, page):
    """Require every canonical answer unit and exact quotes, independent of report order."""
    bank={unit['id']:unit['text'] for unit in answer_unit_bank(question.get('answer'))}
    claims = check.get('answer_claims')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 6:
        raise ValueError('Content review must audit answer_claims for every authored answer')
    indexed=[]
    from core.review_format import normalized_claim, claim_field_errors
    for index, original in enumerate(claims):
        claim = normalized_claim(original)
        errors = claim_field_errors(claim)
        if errors:
            raise ValueError(f'Question {question["id"]} answer_claims[{index}]: '+'; '.join(errors.values()))
        claim_id=claim.get('claim_id')
        if isinstance(claim_id,str) and claim_id.strip().isdigit():claim_id=int(claim_id.strip())
        if type(claim_id) is not int or claim_id not in bank:
            raise ValueError('claim_id must reference a supplied answer_units ID; never infer a missing ID from report position')
        indexed.append((claim_id,claim))
    missing=set(bank)-{claim_id for claim_id,_ in indexed}
    if missing:
        raise ValueError(f'Review every numbered answer unit; missing claim_id values {sorted(missing)}. Reference the supplied IDs without copying or paraphrasing answer text')
    from core.answer_evidence import evidence_policy,evidence_issues
    policy=evidence_policy(question,page)
    issues = []
    for claim_id,claim in indexed:
        prefix = f'Question {question["id"]}: answer unit {claim_id} {bank[claim_id]!r}'
        if not claim['supported']:
            issues.append(prefix+' is unsupported: '+claim['reason'])
        issues.extend(prefix+' '+issue for issue in evidence_issues(claim,question,page,policy=policy))
    return issues


GROUNDING_GUIDANCE = (
    'Audit the authored answer using its Python-supplied answer_units [{id,text}]. '
    'For every unit return an answer_claims record with claim_id equal to its supplied ID, '
    'supported, reason, and evidence [{evidence_id}]. Select IDs ONLY from the same activity\'s '
    'Python-supplied evidence_bank [{id,slot,text}]. These are exact printed excerpts; do not '
    'copy, reconstruct or paraphrase quotes or source IDs. Do not copy or paraphrase the '
    'answer into a claim field. Report units in any order. Judge EVERY assertion within each unit; '
    'supported is false if any part is unsupported, even when other parts are correct. '
    'Each chosen excerpt must be relevant; the chosen excerpts together must prove the WHOLE '
    'unit, including every named detail. Select up to four excerpts when it needs multiple '
    'sources or givens. Each question lists eligible_evidence_ids and required_source_slots. '
    'Cite only eligible IDs and include a required source whenever that list is nonempty. '
    'Matching units contain one or two pairs: verify BOTH printed sides with separate excerpts '
    'when they are in different slots. A shared topic is not evidence: a passage about food drives, '
    'cleaning public spaces and care packages does not support flags, speeches or a different location. '
    'Do not use illustration details or knowledge about typical celebrations. Mark unsupported claims '
    'false even if the rest of the answer is correct. Paraphrases and valid open answers remain allowed '
    'when their meaning is supported. For a calculation or a task without sources, bank entries '
    'whose slot is question_ID may supply printed givens. A source-bound question must use '
    'the named source. Explicit matching givens may additionally cite eligible numbered terms '
    'or choices in captions/questions, but never replace required source evidence. Open-answer criteria can '
    'have an empty evidence list with concrete reasoning. If no excerpt supports a unit, '
    'mark it unsupported and explain why; never select an unrelated excerpt just to fill a record. '
)
