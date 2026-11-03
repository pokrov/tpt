"""Small matching audits and explicit independent-pair cross-checks."""
import re

PAIR=re.compile(r'(?<!\w)([1-8])\s*[:=–—-]\s*([A-H])(?!\w)',re.I)


def matching_key(text, *, pure=False):
    if not isinstance(text,str):return {}
    matches=list(PAIR.finditer(text))
    if not 3<=len(matches)<=8:return {}
    pairs=[(m[1],m[2].upper()) for m in matches]
    if len({n for n,_ in pairs})!=len(pairs) or len({a for _,a in pairs})!=len(pairs):return {}
    if pure and not re.fullmatch(r'[\s,;.]*',PAIR.sub('',text)):return {}
    return dict(pairs)


def matching_answer_units(answer):
    if not matching_key(answer,pure=True):return None
    matches=list(PAIR.finditer(answer));size=1 if len(matches)<=6 else 2
    # Two pairs need at most four excerpts for their two printed sides.
    return [answer[group[0].start():group[-1].end()] for offset in range(0,len(matches),size)
            for group in [matches[offset:offset+size]]]


def is_matching_question(question):
    return bool(re.search(r'\b(?:match(?:ing)?|pair(?:ing)?)\b',question.get('prompt',''),re.I)
                and matching_key(question.get('answer',''),pure=True))


def independent_matching_issues(page,blind):
    issues=[]
    solutions={check.get('id'):check.get('solution','') for check in blind.get('question_checks',[])}
    for question in page.get('exercise',{}).get('questions',[]):
        if not is_matching_question(question):continue
        authored=matching_key(question['answer'],pure=True)
        solved=matching_key(solutions.get(question['id'],''))
        if solved and authored!=solved:
            issues.append(f'Question {question["id"]}: matching key conflicts with the independent solution: '
                f'authored {authored}; independently solved {solved}. Verify each term/description pair '
                'against the printed lists and correct the actual mismatch; positive summary flags '
                'cannot override this disagreement. Preserve source labels, wording and response space.')
    return issues
