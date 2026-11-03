"""Task-focused local copy templates. Sources and answers are never quoted."""
import re

PROFILES = {
    'comprehension': ('Read the source and answer questions using details from the text.', 'Finding details and explaining information from a text', 'short-answer comprehension', 'answer text-based questions'),
    'vocabulary': ('Use context clues to explain the meaning of key terms.', 'Understanding vocabulary in context', 'vocabulary in context', 'explain vocabulary in context'),
    'evidence': ('Distinguish fact from opinion and support responses with evidence from the sources.', 'Distinguishing fact from opinion and citing evidence', 'fact, opinion and supporting evidence', 'support answers with evidence'),
    'correction': ('Identify an inaccurate statement and rewrite it using the source.', 'Checking and correcting statements using a source', 'statement correction', 'check and correct statements'),
    'sequence': ('Arrange events in chronological order and explain the time clues.', 'Sequencing events using time cues', 'chronological sequencing', 'sequence events'),
    'comparison': ('Compare information from the texts and explain similarities or differences.', 'Comparing written information', 'text comparison', 'compare information across texts'),
    'data': ('Interpret the data table, calculate totals and compare groups.', 'Interpreting tables and comparing numerical data', 'data interpretation', 'interpret numerical data'),
    'math': ('Use the given quantities to solve a written word problem.', 'Solving written mathematics word problems', 'word problems', 'solve word problems'),
    'arithmetic': ('Complete the written calculations and explain the results when asked.', 'Solving written mathematics calculations', 'written calculations', 'complete written calculations'),
    'elapsed': ('Use a schedule to calculate durations and work with time intervals.', 'Calculating durations and time intervals', 'schedule and time calculations', 'calculate time intervals'),
}
MATH = {'data', 'math', 'elapsed', 'arithmetic'}


def join_words(items):
    items = list(dict.fromkeys(items))
    if len(items) < 2:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def task_profiles(page):
    """Prefer declared task wording; old records fall back to heading and page text."""
    heading = page.get('heading', '').casefold()
    tasks = page.get('task_prompts')
    body = ('\n'.join(tasks) + '\n' + page.get('task_directions', '')) if tasks else page.get('text', '')
    text = body.casefold()
    found = []
    math_heading = re.search(r'\b(?:data|attendance|elapsed|duration|schedule|math|calculate|calculation|arithmetic|addition|subtraction|multiplication|division)\b|word problem',heading)
    # Heading-specific task types take precedence over incidental source vocabulary.
    if re.search(r'vocabulary|context clues', heading):
        found.append('vocabulary')
    if re.search(r'fact.*(?:opinion|evidence)|opinion', heading) or ('fact or opinion' in text):
        found.append('evidence')
    if re.search(r'true.*false|correct(?:ion|ing)|inaccurate statement', heading):
        found.append('correction')
    if re.search(r'chronolog|sequenc', heading):
        found.append('sequence')
    if re.search(r'compar', heading) or (not math_heading and re.search(r'\b(?:compare|how.*differ|similarities|differences)\b', text)):
        found.append('comparison')
    if re.search(r'elapsed|duration|ceremony.*time|schedule', heading):
        found.append('elapsed')
    elif re.search(r'\bdata\b|attendance|interpret.*table', heading):
        found.append('data')
    elif 'word problem' in heading or re.search(r'\b(?:word problem|how many total|how many.*remaining|calculate the total number)\b', text):
        found.append('math')
    elif re.search(r'\b(?:math|calculate|calculation|arithmetic|addition|subtraction|multiplication|division)\b',heading) or re.search(r'(?m)^\s*(?:calculate|multiply|divide|find the sum)\b',text):
        found.append('arithmetic')
    if not found and re.search(r'\b(?:source|text|read|explain|according to)\b', text):
        found.append('comprehension')
    return list(dict.fromkeys(found))


def activity_description(profiles, page):
    if not profiles:
        return 'Complete the activity using the information provided.'
    if 'comparison' in profiles and 'math' in profiles:
        return 'Compare information in the text and solve a related word problem.'
    if profiles[0] == 'math' and re.search(r'multi[- ]step',page.get('text','')+' '+page.get('task_directions',''),re.I):
        return 'Solve a multi-step word problem using the quantities in the source.'
    # The concise overview describes the main task; additional tasks feed the skills list.
    return PROFILES[profiles[0]][0]


def product_title(topic, kind, grade):
    suffix = ' | Grades ' + grade.replace('-', '–')
    result = f'{topic} {kind}{suffix}'
    if len(result) <= 80:
        return result
    kind = 'Activities' if 'Activities' in kind else 'Worksheets'
    available = 80 - len(kind) - len(suffix) - 1
    if len(topic) > available:
        topic = topic[:available+1].rsplit(' ', 1)[0] if ' ' in topic[:available+1] else topic[:available]
    return topic.rstrip(' ,:;/-') + ' ' + kind + suffix


def varied_copy(pages, topic, grade):
    activities = [page for page in pages if not page.get('continuation')]
    profiles_by_page = [task_profiles(page) for page in activities]
    profiles = list(dict.fromkeys(p for group in profiles_by_page for p in group))
    has_math = bool(MATH.intersection(profiles))
    has_reading = any(p not in MATH for p in profiles)
    if has_math and has_reading:
        kind = 'Reading & Math Activities'
        focus = 'reading comprehension and practical math skills'
    elif has_math:
        kind = 'Math Activities & Worksheets'
        focus = 'mathematical reasoning'
    elif has_reading:
        kind = 'Reading Activities & Worksheets'
        focus = 'reading comprehension and written-response skills'
    else:
        kind = 'Classroom Activities & Worksheets'
        focus = 'classroom skills'
    count = len(activities)
    intro = f'Practice {focus} with {count} {topic} activities for grades {grade}.'
    # Describe a representative mix without copying source facts, questions, tables or solutions.
    actions = [PROFILES[p][3] for p in profiles]
    if len(actions) > 5:
        verbal = [PROFILES[p][3] for p in profiles if p not in MATH][:3]
        numerical = [PROFILES[p][3] for p in profiles if p in MATH][:2]
        actions = verbal + numerical
    detail = 'Students ' + join_words(actions) + '.' if actions else 'Use the individual pages to build a topic-based practice sequence.'
    includes = ['• ' + page['heading'] + ' — ' + activity_description(group,page)
                for page, group in zip(activities, profiles_by_page)]
    skills = ['• ' + PROFILES[p][1] for p in profiles]
    subjects = []
    if has_reading:
        subjects.append('English Language Arts')
    source_text = '\n'.join(p.get('text','') for p in activities)
    if re.search(r'\b(?:historical|history|armistice|military|world war|commemoration)\b', source_text, re.I):
        subjects.append('Social Studies')
    if has_math:
        subjects.append('Mathematics')
    if has_math and has_reading:
        benefit = 'A shared topic connects reading comprehension with practical mathematics. Students practice using written sources alongside numerical information.'
    elif profiles:
        benefit = 'The activities give students several ways to work with information: ' + join_words(PROFILES[p][2] for p in profiles) + '.'
    else:
        benefit = 'Individual activity pages can be selected to fit your topic-based classroom practice.'
    return dict(title=product_title(topic,kind,grade), intro=intro, detail=detail,
                includes=includes, skills=skills, subjects=subjects,
                activities=', '.join(PROFILES[p][2] for p in profiles) or 'Printable classroom activities',
                benefit=benefit, unknown=sum(not p for p in profiles_by_page),
                questions=sum(p['question_count'] for p in activities) if all(type(p.get('question_count')) is int and p['question_count']>0 for p in activities) else None)
