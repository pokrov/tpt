"""Keep Gemini's review grammar small without relaxing local content checks.

Gemini documents HTTP 400 schema-complexity failures for bounded nested arrays:
https://ai.google.dev/gemini-api/docs/structured-output
"""
from copy import deepcopy


def compact_review_schema(schema):
    """Drop nested array cardinalities from transport only; preserve all fields/types.

    The outer page count stays constrained. Question, issue, claim and evidence
    counts remain mandatory in validate_review/claim_issues, including JSON mode.
    Never mutate the authoritative schema or change an authoring request.
    """
    result = deepcopy(schema)

    def visit(node, array_depth=0):
        if isinstance(node, dict):
            is_array = node.get('type') == 'array'
            if is_array and array_depth:
                node.pop('minItems', None)
                node.pop('maxItems', None)
            for value in node.values():
                visit(value, array_depth + int(is_array))
        elif isinstance(node, list):
            for value in node:
                visit(value, array_depth)
    visit(result)
    return result


REVIEW_JSON_CONTRACT = (
    'Return JSON only, with a top-level pages array, one record per supplied page. '
    'Each page has page_number, source_accuracy, no_answer_leak, reason, issues '
    '(0-6 strings), and question_checks (every printed question exactly once). '
    'Each question check has id, source_support, skill_match, answer_correct, '
    'solution, reason and answer_claims (1-6 records). Each claim has claim_id '
    '(an ID from that question\'s supplied answer_units), '
    'supported, reason and evidence (0-4 records). Each evidence record has only '
    'evidence_id, copied from this activity\'s evidence_bank ID. Python resolves its '
    'exact source slot and excerpt; do not return reconstructed quotes or source IDs. '
    'Verdicts are booleans; every claim reason is a concrete nonempty string of at most '
    '250 characters. Evidence must be a list, using [] when none applies. All claims, '
    'answer-unit coverage and quotes are validated locally; JSON mode does not waive any check. '
)
