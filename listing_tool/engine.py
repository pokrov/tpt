"""Pure Python PDF inspection, conservative listing templates and sample export.

No provider imports, network calls, workbook state or generation dependencies.
All page numbers in the public interface are one-based.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from .ocr import PageTextReader

MAX_PAGES = 100
KEY = re.compile(r'^(?:final[ -]page\s+)?(?:answer\s*key|answers\s*(?:and|&)\s*explanations|teacher(?:[’\']s)?\s+(?:guide|answers)|solutions)\b', re.I)
STUDENT = re.compile(r'\bname\s*:|\b(?:reading\s+\d+|activity\s+\d+|check your understanding|read with a purpose)\b', re.I)


def clean(value):
    return re.sub(r'\s+', ' ', value.replace('\ufffd', '-')).strip()


def inspect_pdf(path):
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError('Password-protected PDFs are not supported. Upload an unlocked copy.')
    if not 3 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError('Upload a book with 3 to 100 pages.')
    pages = []
    text_reader = PageTextReader(path)
    try:
        return _inspect_pages(reader, text_reader)
    finally:
        text_reader.close()


def _inspect_pages(reader, text_reader):
    pages = []
    native_cover = ''
    for number, page in enumerate(reader.pages, 1):
        try:
            native = page.extract_text() or ''
        except Exception:
            native = ''
        if number == 1:
            native_cover = native
        extracted = text_reader.read(number-1, native)
        text = extracted['text']
        if len(text) > 100_000:
            raise ValueError('A page contains too much text for this tool.')
        lines = [clean(line) for line in text.splitlines() if clean(line)]
        # A cover may mention an answer key; only a key heading excludes a page.
        is_key = any(KEY.match(line) for line in lines[:4])
        student = bool(STUDENT.search(text)) and not is_key
        cover = number == 1 and not student and not is_key
        role = 'answer key / teacher page' if is_key else 'cover' if cover else 'student' if student else 'unclassified'
        heading_lines = [line for line in lines if not re.match(r'^(?:name\s*:|date\s*:|page\s+\d+)', line, re.I)]
        heading = heading_lines[0] if heading_lines else '(No extractable text)'
        reading = re.match(r'^READING\s+\d+\s*[-:|•–—].*(?:INFORMATIONAL|NARRATIVE|TEXT)', heading, re.I)
        if reading and len(lines) > 1:
            heading = lines[1]
        # Count MCQs from complete sets of answer labels, never cover marketing counts.
        labels = [len(re.findall(r'(?m)^\s*\(' + letter + r'\)\s', text)) for letter in 'ABCD']
        mcq = labels[0] if labels[0] and len(set(labels)) == 1 and student else 0
        pages.append(dict(number=number, text=text, heading=heading[:200], role=role,
                          reading=bool(reading) and student, mcq=mcq,
                          width=round(float(page.mediabox.width), 2),
                          height=round(float(page.mediabox.height), 2),
                          text_method=extracted['method'], ocr_confidence=extracted['confidence'],
                          ocr_title=extracted['title']))
    if sum(len(p['text'].strip()) for p in pages) < 80:
        raise ValueError('No readable text was found, even after offline OCR. Upload a clearer scan with printed text.')
    first = clean(native_cover + '\n' + pages[0]['text'])
    grades = re.search(r'\bGrades?\s*([35])\s*[-–—to ]+\s*([46])\b', first, re.I)
    grade = f'{grades[1]}-{grades[2]}' if grades and (grades[1], grades[2]) in {('3','4'), ('5','6')} else ''
    cover_lines = [clean(line) for line in pages[0]['text'].splitlines() if clean(line)]
    cover_lines = [line for line in cover_lines if not re.match(r'^(?:Grades?\b|THE CLASSROOM|YOUR CLASSROOM|\d+\s+(?:readings?|questions?))', line, re.I)]
    topic = cover_lines[0] if cover_lines and pages[0]['role'] == 'cover' else ''
    native_cover_grade = re.search(r'(?im)^Grades?\s+[35]\s*[-–—]\s*[46]\b', native_cover)
    if topic and pages[0]['text_method'] == 'ocr':
        topic = pages[0]['ocr_title'] or topic
    if topic and (pages[0]['text_method'] != 'ocr' or native_cover_grade):
        fragments = []
        def title_fragment(text, cm, tm, font, size):
            for line in text.splitlines():
                line = clean(line)
                if line and not re.match(r'^(?:Grades?\b|THE CLASSROOM|YOUR CLASSROOM|\d+\s+(?:readings?|questions?))', line, re.I):
                    fragments.append((float(size), line))
        reader.pages[0].extract_text(visitor_text=title_fragment)
        if fragments:
            largest = max(size for size, line in fragments)
            topic = ' '.join(line for size, line in fragments if size == largest)[:180]
    if topic.upper() in {'THE CLASSROOM ACTIVITY COLLECTION', 'YOUR CLASSROOM COLLECTION', 'OUR CLASSROOM COLLECTION'}:
        topic = ''
    return dict(pages=pages, total=len(pages), topic=topic, grade=grade,
                ocr_pages=[p['number'] for p in pages if p['text_method'] == 'ocr'],
                suggested=[p['number'] for p in pages if p['role'] == 'student'][:3])


def select_pages(book, value=''):
    if value.strip():
        if not re.fullmatch(r'\s*\d+\s*,\s*\d+\s*,\s*\d+\s*', value):
            raise ValueError('Enter exactly three different page numbers, separated by commas (for example 2,3,4).')
        chosen = [int(n.strip()) for n in value.split(',')]
    else:
        chosen = book['suggested']
    if len(chosen) != 3 or len(set(chosen)) != 3:
        raise ValueError('Three student pages could not be identified. Enter three page numbers explicitly.')
    if any(n < 1 or n > book['total'] for n in chosen):
        raise ValueError('A selected page number is outside this PDF.')
    if any(book['pages'][n-1]['role'] in {'cover', 'answer key / teacher page'} for n in chosen):
        raise ValueError('Select student pages only. Detected cover, answer-key and teacher pages cannot be used.')
    return chosen


def make_preview(source, target, chosen):
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for number in chosen:
        page = writer.add_page(reader.pages[number-1], excluded_keys=['/Annots', '/AA'])
        page.transfer_rotation_to_content()
        # Remove links, forms and other active annotations from the sample.
        for name in ('/Annots', '/AA'):
            page.pop(name, None)
        box = page.cropbox
        width, height = float(box.width), float(box.height)
        overlay = BytesIO()
        canvas = Canvas(overlay, pagesize=(width, height))
        canvas.setFillColorRGB(.18, .28, .38)
        canvas.setFillAlpha(.19)
        canvas.saveState()
        canvas.translate(width / 2, height / 2)
        canvas.rotate(42)
        canvas.setFont('Helvetica-Bold', min(width / 6.1, 105))
        canvas.drawCentredString(0, 0, 'PREVIEW')
        canvas.restoreState()
        canvas.setFillAlpha(1)
        canvas.setFillColorRGB(.16, .25, .30)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawCentredString(width / 2, 13, f'PREVIEW - Sample page {number} - OUR CLASSROOM COLLECTION')
        canvas.save()
        page.merge_translated_page(PdfReader(overlay).pages[0], float(box.left), float(box.bottom))
        page.pop('/Annots', None)
    writer.add_metadata({'/Title': 'Three student page preview', '/Author': 'OUR CLASSROOM COLLECTION'})
    with Path(target).open('wb') as handle:
        writer.write(handle)


def draft_listing(book, topic='', grade=''):
    topic = clean(topic or book['topic'])
    grade = grade or book['grade']
    if not topic or len(topic) > 180:
        raise ValueError('Enter a short book topic/title (up to 180 characters).')
    if grade not in {'3-4', '5-6'}:
        raise ValueError('Select Grades 3-4 or Grades 5-6; the grade could not be confirmed from this PDF.')
    pages = book['pages']
    student = [p for p in pages if p['role'] == 'student']
    readings = [p for p in student if p['reading']]
    qpages = [p for p in student if p['mcq']]
    questions = sum(p['mcq'] for p in qpages)
    paired = bool(readings) and len(readings) == len(qpages) and all(
        p['number'] < len(pages) and pages[p['number']]['mcq'] == 5 for p in readings)
    from .listing_copy import varied_copy, product_title
    activity_copy = varied_copy(student,topic,grade) if student and not (readings and qpages) else None
    kind = 'Reading Comprehension Passages & Questions' if readings and qpages else 'Printable Classroom Activities'
    title = activity_copy['title'] if activity_copy else product_title(topic,kind,grade)
    intro = (f'Explore {topic} with {len(readings)} reading passages and {questions} multiple-choice questions for grades {grade}.'
             if readings and qpages else f'Explore {topic} with printable classroom pages for grades {grade}.')
    if activity_copy:
        intro = activity_copy['intro']
    includes = []
    for page in readings or [p for p in student if not p.get('continuation')]:
        item = '• ' + page['heading']
        if not activity_copy and page.get('summary'):
            item += ' — ' + page['summary']
        elif not activity_copy and page['reading']:
            paragraph = re.search(r'Read with a purpose\s+1\.\s+(.+?)(?=\s+2\.|Continue to)', page['text'], re.S | re.I)
            if paragraph:
                sentence = re.split(r'(?<=[.!?])\s+', clean(paragraph[1]))[0]
                if len(sentence) <= 400:
                    item += ' — ' + sentence
        includes.append(item)
    if activity_copy:
        includes = activity_copy['includes']
        if activity_copy['questions']:
            includes.append(f'• {activity_copy["questions"]} questions across {len(activity_copy["includes"])} activities')
    if questions:
        includes.append(f'• {questions} multiple-choice questions across {len(qpages)} question pages')
    keys = [p for p in pages if p['role'] == 'answer key / teacher page'
            and re.match(r'^(?:final[ -]page\s+)?answer\s*key\b', p['heading'], re.I)]
    if keys:
        includes.append('• ' + ('Final-page answer key' if len(keys) == 1 and keys[0]['number'] == book['total'] else 'Answer-key section'))
    question_text = '\n'.join(p['text'] for p in qpages) if qpages else '\n'.join(p['text'] for p in student)
    patterns = [('Finding explicit details', r'\b(?:according to|what|where|when|which)\b'),
                ('Making text-based inferences', r'\b(?:infer|inference|most likely|suggests?)\b'),
                ('Understanding vocabulary in context', r'\b(?:word|phrase).{0,60}\b(?:mean|meaning)\b|\bvocabulary\b'),
                ('Identifying reasons and purposes', r'\b(?:why|purpose|reason)\b'),
                ('Comparing written information', r'\b(?:compare|contrast|similar|different|both)\b'),
                ('Sequencing information', r'\b(?:sequence|chronological|correct order)\b'),
                ('Solving written mathematics problems', r'\b(?:calculate|multiply|divide|sum|difference|how many|how much)\b')]
    skills = ['• ' + label for label, pattern in patterns if re.search(pattern, question_text, re.I)]
    if activity_copy:
        skills = activity_copy['skills']
    if not activity_copy and book.get('metadata_source') == 'agent' and book.get('skill_refs'):
        from .product_info import SKILLS
        skills = ['• ' + SKILLS[key] for key in dict.fromkeys(ref['skill'] for ref in book['skill_refs'])]
    notes = ['Offline template draft: review wording, headings, skills and counts before publishing. This listing step makes no provider calls and does not verify educational correctness.']
    if book.get('metadata_source') == 'agent':
        notes.append('Page facts come from the agent’s saved product information matched to this PDF. No OCR was needed.')
    if book.get('metadata_note'):
        notes.append(book['metadata_note'])
    if activity_copy and activity_copy['unknown']:
        notes.append('Some activity descriptions are generic because their task type was unclear. Review those entries before publishing.')
    if book.get('ocr_pages'):
        notes.append('Offline OCR read pages ' + ', '.join(map(str, book['ocr_pages'])) + '. Check names, numbers, headings and page roles against the PDF; scan recognition can make mistakes.')
    if any(p['role'] == 'unclassified' for p in pages):
        notes.append('Some pages are unclassified. Check the page inventory; automatic activity totals may be incomplete.')
    if not paired:
        notes.append('A standard five-question reading-pair structure was not confirmed. No five-per-reading claim was added.')
    if not skills:
        skills = ['• Independent practice with the included activities']
        notes.append('No specific skills were identified confidently. Add the applicable skills after reviewing the book.')
    a4 = all(abs(p['width']-595.28) < 3 and abs(p['height']-841.89) < 3 for p in pages)
    routine = ('Each reading has a separate question page with five multiple-choice questions.'
               if paired else 'Choose individual activities or use the pages together as a topic-based learning pack.')
    if activity_copy:
        routine = activity_copy['detail']
    subjects = []
    if readings or re.search(r'\b(?:source|vocabulary|comprehension|reading)\b', question_text, re.I):
        subjects.append('English Language Arts')
    if readings:
        subjects.append('Reading')
    if '• Solving written mathematics problems' in skills:
        subjects.append('Mathematics')
    if activity_copy:
        subjects = activity_copy['subjects']
    breakdown = []
    if any(p['role'] == 'cover' for p in pages):
        breakdown.append('cover')
    if readings:
        breakdown.append(f'{len(readings)} reading pages')
    if qpages:
        breakdown.append(f'{len(qpages)} question pages')
    if not readings and student:
        breakdown.append(f'{len(student)} student activity pages')
    if keys:
        breakdown.append(f'{len(keys)} answer-key page' + ('s' if len(keys) != 1 else ''))
    complete = sum(p['role'] != 'unclassified' for p in pages) == len(pages) and (not readings or len(readings)+len(qpages) == len(student))
    # Do not invent topic summaries, vocabulary, explanations or visual styles.
    text = '\n'.join([
        'TITLE', title, '', 'DESCRIPTION', intro, '', routine, '',
        'WHAT’S INCLUDED', *(includes or ['• Printable pages from the uploaded book']), '',
        'SKILLS PRACTICED', *skills, '', 'WAYS TO USE',
        ('Use selected pages for targeted practice, small-group instruction, classroom centers, or independent review. Combine activities to create a topic-based lesson sequence.' if activity_copy else
         'Use these printable pages for classroom centers, small-group lessons, independent practice, or topic-based sessions. Select individual pages or work through the pack over several lessons.'), '',
        'WHY IT’S USEFUL',
        (activity_copy['benefit'] + (' A final answer key supports checking completed work.' if keys else '') if activity_copy else
         'The printable format lets you select pages for your classroom routine and revisit them during related lessons.'), '',
        'PRODUCT DETAILS', f'Pages: {book["total"]} total' + (' — ' + ', '.join(breakdown) if complete and breakdown else ' in the full book'), f'Grades: {grade}',
        'Subjects: ' + (', '.join(subjects) if subjects else 'Classroom learning'),
        'Activities: ' + activity_copy['activities'] if activity_copy else 'Activities: Reading passages and multiple-choice comprehension' if readings and qpages else 'Activities: Printable written activities',
        'Format: Printable PDF' + ('; A4 portrait' if a4 else '; original page sizes'),
        'Preview: Three student pages with PREVIEW watermarks; supplied separately from the full book', '',
        'Digital download only. No physical product will be shipped.',
        'Created by OUR CLASSROOM COLLECTION.'
    ])
    return dict(title=title, listing=text, notes=notes)
