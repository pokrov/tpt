"""Repair malformed review metadata without replacing valid audits or workbook text."""
from copy import deepcopy
import json

CLAIM_REASON_LIMIT = 250


class ReviewFormatError(ValueError):
    def __init__(self, response, targets):
        self.response = response
        self.targets = targets
        descriptions = [f"Activity {t['page_number']} Question {t['question_id']} "
                        f"answer_claims[{t['claim_index']}]: "+'; '.join(t['errors'].values())
                        for t in targets]
        super().__init__('Review response format: '+'; '.join(descriptions))


def normalized_claim(claim):
    """Resolve explicit serialization variants only; never infer a verdict or evidence."""
    result = deepcopy(claim)
    if not isinstance(result, dict):
        return result
    supported = result.get('supported')
    if isinstance(supported, str) and supported.strip().casefold() in ('true', 'false'):
        result['supported'] = supported.strip().casefold() == 'true'
    if isinstance(result.get('reason'), str):
        result['reason'] = ' '.join(result['reason'].split())
    evidence = result.get('evidence')
    if isinstance(evidence, dict) and (set(evidence) == {'evidence_id'} or set(evidence) == {'slot', 'quote'}):
        result['evidence'] = [evidence]
    return result


def claim_field_errors(claim):
    if not isinstance(claim, dict):
        return {field:'claim must be an object with '+field for field in ('claim_id','supported','evidence','reason')}
    errors = {}
    claim_id = claim.get('claim_id')
    if not (type(claim_id) is int or isinstance(claim_id, str) and claim_id.strip().isdigit()):
        errors['claim_id'] = 'claim_id must be an explicit integer answer-unit ID'
    if type(claim.get('supported')) is not bool:
        errors['supported'] = 'supported must be an explicit boolean true or false'
    evidence = claim.get('evidence')
    if not isinstance(evidence, list):
        errors['evidence'] = 'evidence must be a list, including [] when no evidence applies'
    elif len(evidence) > 4:
        errors['evidence'] = f'evidence has {len(evidence)} records; at most 4 are allowed'
    reason = claim.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        errors['reason'] = 'reason must be a nonempty concrete explanation'
    elif len(reason) > CLAIM_REASON_LIMIT:
        errors['reason'] = f'reason has {len(reason)} characters; limit is {CLAIM_REASON_LIMIT}; explain concisely without changing the verdict'
    return errors


def prepare_review(raw,pages=None):
    """Normalize harmless encodings and report all malformed claim fields together."""
    response = deepcopy(raw)
    targets = []
    expected={page['page_number']:page for page in pages or []}
    rows = response.get('pages') if isinstance(response, dict) else None
    if not isinstance(rows, list):
        return response  # The authoritative review validator reports structural errors.
    for row_index, row in enumerate(rows):
        checks = row.get('question_checks') if isinstance(row, dict) else None
        if not isinstance(checks, list):
            continue
        for check_index, check in enumerate(checks):
            claims = check.get('answer_claims') if isinstance(check, dict) else None
            if not isinstance(claims, list) or not 1 <= len(claims) <= 6:
                continue
            for claim_index, original in enumerate(claims):
                claim = claims[claim_index] = normalized_claim(original)
                errors = claim_field_errors(claim)
                number=row.get('page_number')
                page=expected.get(number) if type(number) is int else None
                question=next((q for q in page['exercise']['questions'] if q['id']==check.get('id')),None) if page else None
                if question and not {'evidence','supported'}.intersection(errors):
                    from core.answer_evidence import evidence_issues
                    try:
                        citation_errors=evidence_issues(claim,question,page)
                    except ValueError as error:
                        citation_errors=[str(error)]
                    if citation_errors:errors['evidence']='; '.join(citation_errors)
                if errors:
                    targets.append({'target_id':f'R{len(targets)+1}', 'page_number':row.get('page_number'),
                        'question_id':check.get('id'), 'claim_index':claim_index, 'errors':errors,
                        'path':(row_index,check_index,claim_index)})
    if targets:
        raise ReviewFormatError(response, targets)
    return response


def repair_schema(targets):
    from core.answer_grounding import claim_schema
    from core.response_schemas import obj, array, text
    from core.review_transport import compact_review_schema
    return compact_review_schema(obj({'corrections':array(obj({'target_id':text(12),
        'claim':claim_schema()['items']}),len(targets),len(targets))}))


def repair_prompt(base, targets, error):
    public = [{k:v for k,v in target.items() if k != 'path'} for target in targets]
    return ('Correct REVIEW RESPONSE FORMAT ONLY, including citation provenance. The workbook, answer units and evidence bank '
        'in the original request are immutable. Do not return activities, HTML, images or a new '
        'book review. Return {"corrections":[{"target_id":"R1","claim":'
        '{"claim_id":1,"supported":true,"evidence":[{"evidence_id":"E1"}],'
        '"reason":"Concise concrete explanation, at most 250 characters."}}]}. '
        'This is a shape example, not a verdict or evidence to copy. Return every listed target '
        'exactly once. Only fields listed in errors may change; Python pins all other values, '
        'including negative verdicts, valid source references and unaffected reviews. For a bad '
        'citation, reassess this exact unit against eligible_evidence_ids and required_source_slots. '
        'Select exact supporting excerpts; never invent missing evidence or merely choose a related '
        'topic. If the source cannot support the unit, return supported:false and explain why. '
        'Python allows a new negative verdict but never reverses an existing negative verdict. '
        'Matching pairs must cite both printed sides. Use [] only where no evidence applies. '
        'Keep all reasons concrete and <=250 characters. Validation: '+str(error)+
        '\nCorrection targets:\n'+json.dumps(public)+
        '\nRetained review response:\n'+json.dumps(base))


def merge_repair(base, targets, raw):
    corrections = raw.get('corrections') if isinstance(raw, dict) else None
    if not isinstance(corrections, list) or len(corrections) != len(targets):
        raise ValueError('Review format correction must return every target exactly once')
    expected = {t['target_id']:t for t in targets}
    result = deepcopy(base)
    seen = set()
    for correction in corrections:
        target_id = correction.get('target_id') if isinstance(correction, dict) else None
        if not isinstance(target_id, str) or target_id not in expected or target_id in seen:
            raise ValueError('Review format correction has an unknown or repeated target_id')
        seen.add(target_id)
        target = expected[target_id]
        proposed = normalized_claim(correction.get('claim'))
        if not isinstance(proposed, dict) or any(field not in proposed for field in target['errors']):
            raise ValueError('Review format correction must supply every malformed field')
        row, check, claim = target['path']
        claims = result['pages'][row]['question_checks'][check]['answer_claims']
        retained = claims[claim] if isinstance(claims[claim], dict) else {}
        for field in target['errors']:
            retained[field] = deepcopy(proposed[field])
        if 'evidence' in target['errors'] and proposed.get('supported') is False:
            retained['supported']=False
            if isinstance(proposed.get('reason'),str) and proposed['reason'].strip() and len(proposed['reason'])<=CLAIM_REASON_LIMIT:
                retained['reason']=proposed['reason']
        claims[claim] = retained
    return result
