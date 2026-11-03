"""Catch numeric contradictions between a blind solution and verified exact math."""
from fractions import Fraction
import re

from core.exercise_quality import expected_calculation, normalize_calculation, numeric_display_text


def single_numeric_solution(text):
    """Read one explicit result, never guess among intermediates or written labels."""
    if not isinstance(text, str):
        return None
    # Percentages and clock times need contextual unit conversion; leave these
    # to the source/units review instead of guessing their numeric representation.
    if '%' in text or re.search(r'\d:\d', text):
        return None
    text = numeric_display_text(text).replace('−', '-')
    tokens = re.findall(r'(?<![\w.])-?(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+)\s*%?(?![\w.]\d)', text)
    if len(tokens) != 1:
        return None
    token = tokens[0].strip()
    token = token.rstrip('%').strip()
    try:
        if re.fullmatch(r'-?\d+\s+\d+/\d+', token):
            whole, fraction = token.split()
            result = abs(Fraction(whole)) + Fraction(fraction)
            result = -result if whole.startswith('-') else result
        else:
            result = Fraction(token)
        return result
    except (ValueError, ZeroDivisionError):
        return None


def independent_math_issues(page, review):
    """Require a fresh review if exact arithmetic contradicts the independent result."""
    questions = {q['id']: q for q in page['exercise']['questions']}
    issues = []
    for check in review['question_checks']:
        question = questions[check['id']]
        calculation = question.get('calculation')
        if not isinstance(calculation, dict):
            continue
        result = single_numeric_solution(check.get('solution'))
        if result is None:
            continue
        expected = expected_calculation(normalize_calculation(calculation['expression']), question['prompt'])
        if result != expected:
            issues.append(f'Question {check["id"]}: independent solution gives {result}, but exact '
                          f'calculation gives {expected}. Re-solve from the printed quantities and units; '
                          'align the source, prompt, calculation and answer key. Do not approve conflicting results.')
    return issues
