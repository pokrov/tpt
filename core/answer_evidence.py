"""Shared exact citation eligibility for prompts and authoritative validation."""
import re


def evidence_policy(question,page):
    from core.answer_grounding import normalized,source_records
    from core.matching_grounding import is_matching_question,matching_key
    records=source_records(page);prompt=question['prompt']
    personal=bool(re.search(r'\b(?:your own|your opinion|personally|imagine|suggest|propose|recommend|in your view)\b',prompt,re.I))
    source_bound=bool(re.search(r'\b(?:based on|according to|from|using)\b.{0,80}\b(?:text|source|passage|card|evidence)\b',prompt,re.I))
    substantive=any(slot=='passage' or slot.startswith('stimulus_') or len(text.split())>=6 or re.search(r'\d',text)
                    for slot,text in records.items())
    needs_source=substantive and not isinstance(question.get('calculation'),dict) and not (personal and not source_bound)
    allowed=dict(records);named=set()
    for source in page.get('exercise',{}).get('stimuli',[]) or []:
        label=source.get('label') if isinstance(source,dict) else None
        if isinstance(label,str) and re.search(r'(?<!\w)'+re.escape(normalized(label).rstrip(':'))+r'(?!\w)',normalized(prompt)):
            named.add('stimulus_'+source['id'])
    if needs_source and len(named)==1:allowed={slot:text for slot,text in allowed.items() if slot in named}
    required=set(allowed) if needs_source else set()
    if not needs_source:
        allowed['question_'+question['id']]=prompt
    elif is_matching_question(question):
        # Printed matching givens supplement, never replace, required sources.
        pairs=matching_key(question['answer'],pure=True)
        for slot,text in records.items():
            marker=re.match(r'^\s*([1-8]|[A-H])[.)]\s+\S',text)
            if slot.startswith('caption_') and marker and marker[1] in set(pairs)|set(pairs.values()):
                allowed[slot]=text
        numbers=re.findall(r'(?<!\w)([1-8])[.)]\s+\S',prompt)
        if len(numbers)==len(set(numbers)) and set(numbers)==set(pairs):
            allowed['question_'+question['id']]=prompt
    return {'allowed':allowed,'required':required}


def evidence_issues(claim,question,page, *, policy=None):
    from core.answer_grounding import normalized,evidence_bank,source_records
    policy=policy or evidence_policy(question,page)
    allowed=policy['allowed'];records=source_records(page)
    records['question_'+question['id']]=question['prompt']
    excerpts={entry['id']:entry for entry in evidence_bank(page)}
    issues=[];valid_slots=set()
    for supplied in claim['evidence']:
        evidence=supplied
        if isinstance(evidence,dict) and 'evidence_id' in evidence:
            evidence_id=evidence['evidence_id']
            if not isinstance(evidence_id,str) or evidence_id not in excerpts:
                issues.append('references an unknown evidence_id; select an ID from this activity\'s evidence_bank');continue
            if set(evidence)!={'evidence_id'}:
                raise ValueError('Numbered evidence must contain only evidence_id; never override its canonical source or quote')
            entry=excerpts[evidence_id];evidence={'slot':entry['slot'],'quote':entry['text']}
        if (not isinstance(evidence,dict) or not isinstance(evidence.get('slot'),str)
                or not isinstance(evidence.get('quote'),str) or not evidence['quote'].strip()
                or len(evidence['slot'])>40 or len(evidence['quote'])>300):
            raise ValueError('Claim evidence needs an exact slot ID and a nonempty verbatim quote')
        slot=evidence['slot'];quote=normalized(evidence['quote'])
        if slot not in records:
            issues.append('references an unknown printed-source slot; select a supplied evidence_id')
        elif quote not in normalized(records[slot]):
            issues.append('cites evidence that is absent from its printed source; never invent an excerpt')
        elif slot not in allowed:
            issues.append(f'cites existing printed source {slot!r} that this question does not permit; '
                          'select an eligible_evidence_id and retain required_source_slots')
        else:valid_slots.add(slot)
    if claim['supported'] and policy['required'] and not valid_slots.intersection(policy['required']):
        issues.append('has no supporting printed-source evidence from the required sources; correct the citation '
                      'or mark unsupported if the actual source cannot support the unit')
    return issues


def evidence_contract(question,page):
    from core.answer_grounding import evidence_bank
    policy=evidence_policy(question,page)
    return {'eligible_evidence_ids':[entry['id'] for entry in evidence_bank(page) if entry['slot'] in policy['allowed']],
            'required_source_slots':sorted(policy['required'])}
