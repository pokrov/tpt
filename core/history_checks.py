"""Narrow checks for verified Veterans Day errors, without rewriting lessons silently.

References: department.va.gov/veterans-day/history-of-veterans-day/ and
defense.gov/News/Feature-Stories/story/Article/1675470/5-facts-to-know-about-veterans-day/
"""
import re


def history_guidance():
    return ('For Veterans Day history: the armistice took effect at 11 a.m. on November 11, 1918; '
            'do not say it was signed at that hour. November 11 is a date, not an exact hour. '
            'Veterans Day honors all who served, living and deceased, with particular emphasis '
            'on thanking living veterans. If repairing a false claim, update the printed source, '
            'dependent question and final key together; do not preserve a false source to match a key. ')


def history_issues(page):
    exercise = page.get('exercise', {})
    sources = [exercise.get('passage','')]
    sources += [r.get('text','') for field in ('stimuli','captions')
                for r in (exercise.get(field) or []) if isinstance(r,dict)]
    sources = [text for text in sources if isinstance(text,str)]
    questions = exercise.get('questions', [])
    context = ' '.join([str(page.get('title',''))]+sources+[q.get('prompt','') for q in questions])
    if not re.search(r'\b(?:Veterans Day|armistice|World War I|WWI)\b',context,re.I):
        return []
    wwi = bool(re.search(r'\b(?:1918|World War I|WWI)\b',context,re.I))
    issues = []
    for text in sources:
        if wwi and re.search(r'\barmistice\b[^.!?]{0,80}\bsigned\s+(?:at\s+)?(?:the\s+)?(?:eleventh hour|11\s*a\.?m\.?)',text,re.I):
            issues.append('The armistice took effect at 11 a.m.; it was signed earlier. Correct the source and dependent key together instead of treating signing and taking effect as the same event.')
        if re.search(r'\b(?:November\s+11(?:th)?|11(?:th)?\s+November)\s+marks\s+the\s+exact\s+hour\b',text,re.I):
            issues.append('November 11 is a date, not an exact hour. State that the armistice took effect at 11 a.m. on that date; update dependent matching descriptions and key too.')
        definition = re.search(r'\bVeterans Day\b[^.!?]{0,120}\b(?:honors?|to honor)\s+(?:all\s+|only\s+)?living\s+(?:military\s+)?veterans\b',text,re.I)
        emphasis = re.search(r'\b(?:especially|particularly|primarily|special emphasis)\b',text,re.I)
        if definition and (not emphasis or re.search(r'\bonly\s+living\b',text,re.I)):
            issues.append('Define Veterans Day as honoring all veterans, living and deceased; it especially thanks living veterans. Correct the source and dependent answers together.')
    for q in questions:
        text = q.get('prompt','')+' '+q.get('answer','')
        if (re.search(r'\b(?:eleventh hour|11\s*(?:a\.?m\.?|AM))\b',text,re.I)
                and wwi and re.search(r'\barmistice\b',context,re.I)
                and re.search(r'\b(?:was\s+)?signed\b',q.get('answer',''),re.I)
                and not re.search(r'\b(?:took effect|went into effect|became effective|ceasefire began|fighting stopped)\b',q.get('answer',''),re.I)):
            issues.append(f'Question {q.get("id")}: the 11 a.m. event was the armistice taking effect, not its signing. Correct the answer and any dependent source wording together.')
    return issues
