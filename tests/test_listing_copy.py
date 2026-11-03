"""Listing copy describes student tasks instead of dumping source evidence."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from listing_tool.engine import draft_listing
from listing_tool.listing_copy import product_title
from listing_tool.product_info import read_product_info, write_product_info
from tests.test_listing_library import canonical_story
from tests.test_listing_tool import fixture


def varied_book(grade='5-6'):
    headings = ['Origins of the Observance','Honoring All Who Served','Vocabulary in Context',
                'Fact and Supporting Evidence','True or False Correction','Chronological Sequence',
                'Comparing Commemorations','Parade Attendance Data','Community Donation Math','Ceremony Elapsed Time']
    tasks = ['Read the historical source and explain the reason for the observance.',
             'How does the focus differ? How many total items were distributed?',
             'Use context clues to explain the word.',
             'Classify the statement as fact or opinion and cite evidence.',
             'Identify the error and rewrite the statement correctly.',
             'Arrange the events in chronological order using the time clues.',
             'Compare practices in the two sources.',
             'Calculate combined totals and compare the groups in the table.',
             'Read the details and solve the multi-step word problem.',
             'Use the schedule to calculate durations.']
    cover = dict(number=1,role='cover',heading='Veterans Day',text='',reading=False,mcq=0,width=595.28,height=841.89)
    pages = [cover]
    for i,(heading,task) in enumerate(zip(headings,tasks),2):
        raw = 'Source A: PRIVATE_SOURCE. Card A: 1,250 items. Event Name | Start Time | End Time --- | --- | --- 08:30 AM 09:15 AM'
        pages.append(dict(number=i,role='student',heading=heading,text=raw+'\n'+task,
                          summary=raw,question_count=1 if i in (6,10) else 2,
                          reading=False,mcq=0,width=595.28,height=841.89))
    pages.append({**cover,'number':12,'role':'answer key / teacher page','heading':'Answer Key'})
    return dict(topic='Veterans Day',grade=grade,total=12,pages=pages,metadata_source='agent',skill_refs=[],ocr_pages=[])


class ListingCopyTests(unittest.TestCase):
    def test_reported_varied_listing_has_task_descriptions_and_no_source_dump_both_grades(self):
        for grade in ('3-4','5-6'):
            book=varied_book(grade)
            before=deepcopy(book)
            result=draft_listing(book)
            text=result['listing']
            self.assertEqual(book,before)
            self.assertIn('Reading & Math Activities',result['title'])
            self.assertIn('10 Veterans Day activities',text)
            self.assertIn('18 questions across 10 activities',text)
            self.assertIn('Use a schedule to calculate durations',text)
            self.assertIn('Distinguish fact from opinion',text)
            self.assertIn('Solve a multi-step word problem',text)
            self.assertIn('Subjects: English Language Arts, Social Studies, Mathematics',text)
            for bad in ('PRIVATE_SOURCE','Source A:','Card A:','Event Name','08:30','1,250','| ---',
                        'Explore Veterans Day with printable classroom pages','The printable format lets you'):
                self.assertNotIn(bad,text)

    def test_canonical_tasks_override_incidental_source_keywords(self):
        book=varied_book()
        book['pages']=book['pages'][:1]+[book['pages'][1]]+[book['pages'][-1]]
        page=book['pages'][1]
        page.update(heading='Understanding a Passage',text='A historical source discusses how leaders compare data and solve a word problem.',
                    task_prompts=['What happened in the passage?'],task_directions='Read the source and answer the question.',question_count=1)
        result=draft_listing(book)
        self.assertNotIn('Math',result['title'])
        self.assertNotIn('word problems',result['listing'])
        self.assertIn('Read the source and answer questions',result['listing'])

    def test_math_only_and_unknown_pages_do_not_invent_reading_skills(self):
        book=varied_book()
        book['pages']=[book['pages'][0],book['pages'][8],book['pages'][10],book['pages'][-1]]
        result=draft_listing(book)
        self.assertIn('Math Activities',result['title'])
        self.assertNotIn('English Language Arts',result['listing'])
        book['pages'][1].update(heading='Practice Page',text='Name: ________',summary='Do not copy me')
        book['pages'][2].update(heading='Another Page',text='Name: ________',summary='Do not copy me')
        result=draft_listing(book)
        self.assertIn('Classroom Activities',result['title'])
        self.assertNotIn('Do not copy me',result['listing'])
        self.assertTrue(any('task type was unclear' in note for note in result['notes']))

    def test_continuations_do_not_add_activities_or_repeat_bullets(self):
        book=varied_book()
        continuation=deepcopy(book['pages'][1]); continuation['continuation']=True
        book['pages'].insert(2,continuation)
        result=draft_listing(book)
        self.assertIn('10 Veterans Day activities',result['listing'])
        self.assertEqual(result['listing'].count('• Origins of the Observance'),1)

    def test_long_titles_fit_without_losing_grade_or_splitting_words(self):
        title=product_title('Veterans Day Historical Sources and Community Commemoration Learning Activities for Elementary Students',
                            'Reading & Math Activities','5-6')
        self.assertLessEqual(len(title),80)
        self.assertTrue(title.endswith(' | Grades 5–6'))
        self.assertNotIn('Commemora Activities',title)

    def test_plain_arithmetic_is_not_advertised_as_a_word_problem(self):
        from listing_tool.listing_copy import task_profiles, activity_description
        page=dict(heading='Calculate',text='Calculate the sum: 12 + 8.')
        profiles=task_profiles(page)
        self.assertEqual(profiles,['arithmetic'])
        self.assertNotIn('word problem',activity_description(profiles,page))

    def test_new_metadata_preserves_prompts_and_directions_without_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf=Path(folder)/'book.pdf'; fixture(pdf)
            story=canonical_story()
            path=write_product_info(story,pdf,[1]*10)
            book=read_product_info(pdf)
            self.assertEqual(book['pages'][2]['task_prompts'],['What does this passage explain?']*5)
            self.assertNotIn('PRIVATE_SOLUTION',path.read_text())
            self.assertNotIn('PRIVATE_KEY_EXPLANATION',path.read_text())
            self.assertIn('5 reading passages and 25 multiple-choice questions',draft_listing(book)['listing'])

    def test_invalid_new_task_fields_rejected_and_legacy_files_still_supported(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            pdf=Path(folder)/'book.pdf'; fixture(pdf)
            path=write_product_info(canonical_story(),pdf,[1]*10)
            data=json.loads(path.read_text())
            data['pages'][2]['task_prompts']=['Wrong count']
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'task prompts'):
                read_product_info(pdf)
            for page in data['pages']:
                page.pop('task_prompts',None); page.pop('task_directions',None)
            path.write_text(json.dumps(data))
            self.assertEqual(read_product_info(pdf)['metadata_source'],'agent')
