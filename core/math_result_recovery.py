"""Derive declared calculation results without asking a language model to perform arithmetic."""
from copy import deepcopy
from fractions import Fraction
import re

from core.exercise_quality import expected_calculation,normalize_calculation,rounding_precision


NUMBER = re.compile(r'(?<![\w.])[-−]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:/\d+)?(?!\w|\.\d|/\d)')


def repair_calculation_metadata(page: dict, question_id: str) -> dict | None:
    """Compute only an incorrect declared result; leave ambiguous prose for scoped review."""
    exercise=page.get('exercise') if isinstance(page,dict) else None
    questions=exercise.get('questions') if isinstance(exercise,dict) else None
    matches=[q for q in questions if isinstance(q,dict) and str(q.get('id'))==question_id] if isinstance(questions,list) else []
    if len(matches)!=1 or not isinstance(matches[0].get('calculation'),dict):return None
    question=matches[0];calculation=question['calculation']
    try:
        expression=normalize_calculation(calculation.get('expression'))
        actual=expected_calculation(expression,question.get('prompt',''))
    except (ValueError,TypeError,ZeroDivisionError):return None
    try: supplied=Fraction(str(calculation.get('answer')))
    except (ValueError,TypeError,ZeroDivisionError): supplied=None
    if supplied==actual:return None
    result=deepcopy(page)
    target=next(q for q in result['exercise']['questions'] if str(q.get('id'))==question_id)
    target['calculation']={**calculation,'expression':expression,'answer':format_result(actual,question.get('prompt',''))}
    return result


def requested_quantity_result(prompt,answer,token,tokens):
    """Identify a stated result for the exact noun requested, never contextual givens."""
    if token is not tokens[0] or not re.fullmatch(r'there\s+(?:are|is|will be)\s*',answer[:token.start()].strip(),re.I):
        return False
    requested=re.search(r'\bhow many\s+([A-Za-z][A-Za-z -]{0,60}?)\s+(?:are|is|were|was|do|does|did|will|remain|remains|can)\b',prompt,re.I)
    if not requested:return False
    noun=' '.join(requested[1].split())
    tail=answer[token.end():]
    if not re.match(r'\s*'+re.escape(noun)+r'\b',tail,re.I):return False
    if re.search(r'\b(?:and|or|if|but|than|between|versus|instead|not)\b',answer,re.I):return False
    def number(text):return Fraction(text.replace(',','').replace('−','-'))
    try:
        givens={number(m[0]) for m in NUMBER.finditer(prompt)}
        return all(number(m[0]) in givens for m in tokens[1:])
    except (ValueError,ZeroDivisionError):return False


def prose_answer_repair_messages(system,page,question_id,error,answer_limit=180):
    """Give prose-only math repair its immutable verified result, not arithmetic design advice."""
    import json
    questions=page.get('exercise',{}).get('questions',[])
    matches=[q for q in questions if str(q.get('id'))==question_id]
    if len(matches)!=1 or not isinstance(matches[0].get('calculation'),dict):return None
    question=matches[0];calculation=question['calculation']
    try:
        expression=normalize_calculation(calculation.get('expression'))
        result=format_result(expected_calculation(expression,question['prompt']),question['prompt'])
    except (ValueError,TypeError,ZeroDivisionError):return None
    exercise=page.get('exercise',{})
    retained={'id':question_id,'prompt':question['prompt'],'original_answer':question.get('answer'),
        'calculation':calculation,'python_verified_result':result,
        'printed_sources':{k:exercise[k] for k in ('passage','stimuli','captions') if k in exercise}}
    return [system,{'role':'user','content':
        'Correct ONLY the answer field for the retained question. Return JSON '
        '{"exercise":{"questions":[{"id":'+json.dumps(question_id)+',"answer":"correct concise prose"}]}}. '
        'The calculation and prompt are immutable. Python has already verified the exact numeric result: '+result+'. '
        'Use that result in an accurate answer to the printed question, preserving units and any essential '
        'context. Do not recalculate, change quantities, choose another operation, replace the task, '
        'or return calculation, prompt, space_mm, HTML or images. Never invent a calendar date or weekday; '
        'use only retained printed facts. Keep the answer within '+str(answer_limit)+' characters. '
        'Validation: '+str(error)+'\nRetained question and facts:\n'+json.dumps(retained)}]


def format_result(value: Fraction, prompt: str) -> str:
    """Print explicitly rounded results as decimals without floating point loss."""
    places = rounding_precision(prompt)
    if places is None or places == 0:
        return str(value)
    scaled = value * 10 ** places
    if scaled.denominator != 1:
        raise ValueError('Rounded result does not match its declared precision')
    sign = '-' if scaled < 0 else ''
    digits = str(abs(scaled.numerator)).zfill(places + 1)
    return sign + digits[:-places] + '.' + digits[-places:]


def repair_declared_result(page: dict, question_id: str) -> dict | None:
    """Correct one unambiguous numeric key result; keep the authored operation and question."""
    exercise = page.get('exercise') if isinstance(page,dict) else None
    questions = exercise.get('questions') if isinstance(exercise,dict) else None
    matches = [q for q in questions if isinstance(q,dict) and str(q.get('id'))==question_id] if isinstance(questions,list) else []
    if len(matches)!=1:
        return None
    question = matches[0]
    calculation = question.get('calculation')
    answer,prompt = question.get('answer'),question.get('prompt')
    if not isinstance(calculation,dict) or not isinstance(answer,str) or not isinstance(prompt,str):
        return None
    try:
        expression = normalize_calculation(calculation.get('expression'))
        actual = expected_calculation(expression,prompt)
        supplied = Fraction(str(calculation.get('answer')))
    except (ValueError,TypeError,ZeroDivisionError):
        return None
    tokens = list(NUMBER.finditer(answer))
    if not tokens:
        return None
    candidates = []
    for token in tokens:
        raw = token[0].replace(',','').replace('−','-')
        try:
            value = Fraction(raw)
        except (ValueError,ZeroDivisionError):
            continue
        # A leading result can retain its unit and explanation. When other
        # numbers follow, it must match the declared or verified result;
        # numbers inside success criteria are not assumed to be answers.
        prefix = answer[:token.start()].strip()
        leading = token is tokens[0] and re.fullmatch(r'(?:(?:answer|result)(?:\s+is)?\s*[:=]?\s*|(?:about|approximately)\s+)?[$£€]?\s*',prefix,re.I)
        # A single declarative result sentence identifies its result just as
        # clearly as a leading '40 shapes'. Never rewrite acceptance criteria,
        # comparative claims, conditions or a multi-number explanation.
        declarative = (len(tokens)==1 and re.fullmatch(
            r'(?:the\s+)?(?:total(?:\s+(?:number|amount|count))?|sum|difference|product|quotient|perimeter|area)'
            r'(?:\s+of\s+[A-Za-z][A-Za-z ,\x27-]{0,80})?\s+is\s*', prefix, re.I))
        percent = bool(re.match(r'\s*%',answer[token.end():]))
        close = value==actual
        if '.' in raw and '/' not in raw:
            places = len(raw.split('.',1)[1])
            if places<=4:
                close = close or value==expected_calculation(expression,f'Round to {places} decimal places.')
        equation_result = False
        if prefix.endswith('='):
            try:
                # Only a complete copy of the retained operation identifies a
                # result token. Never infer an operation from a prose explanation.
                equation_result = normalize_calculation(prefix[:-1].strip()) == expression
            except (ValueError, TypeError):
                pass
        requested=requested_quantity_result(prompt,answer,token,tokens)
        if (leading and (len(tokens)==1 or value in {supplied,actual})) or declarative or requested or equation_result or (percent and close):
            candidates.append((token,value))
    if len(candidates)!=1:
        return None  # Multi-step or ambiguous prose still needs semantic repair.
    token,value = candidates[0]
    if supplied==actual and value==actual:
        return None
    result = deepcopy(page)
    target = next(q for q in result['exercise']['questions'] if str(q.get('id'))==question_id)
    formatted = format_result(actual,prompt)
    if supplied != actual:
        target['calculation'] = {**calculation,'expression':expression,'answer':formatted}
    target['answer'] = answer[:token.start()]+formatted+answer[token.end():]
    return result
