"""Regress numeric metadata, grade revision and multi-number prose drift."""
from copy import deepcopy
from fractions import Fraction
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from core.creative_generator import ask_json,layout_contract,validate_design
from core.math_result_recovery import repair_declared_result,repair_calculation_metadata
from core.response_schemas import design_schema
from tests.coherent_fixtures import authored_page
from tests.test_student_workbook import workbook_config

PROMPT=('Each of 6 branches receives 345 requests daily; 48 at each branch are priority requests. '
        'How many standard requests are processed across all 6 branches each day?')
WRONG='There are 342 standard requests processed across all 6 branches each day.'
RIGHT=WRONG.replace('342','1782')


def library_page():
    page=authored_page(mechanic='word_problems')
    page['exercise'].update(goal='Solve a library request problem.',directions='Use the printed quantities to solve this library practice problem.')
    page['exercise']['questions'][0].update(prompt=PROMPT,answer=WRONG,
        calculation={'expression':'345*6-(48*6)','answer':1782})
    return page


def weak_page():
    page=library_page();page['exercise']['questions'][0].update(
        prompt='Processing takes 3 days and delivery takes 2 days. How many days until pickup?',
        answer='The book will be ready for pickup on the following Monday.',
        calculation={'expression':'3+2','answer':'Monday'})
    return page


def validate(page,band):
    config=workbook_config(band,simple=True)
    return validate_design(page,config['student_font_pt'],quality=config,
        expected_title='Library Practice',require_coherent=True)


def ask(responses,band):
    api=Mock();api.chat.completions.create.side_effect=[SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=json.dumps(p)),finish_reason='stop')]) for p in responses]
    config=workbook_config(band,simple=True)
    with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
         patch('core.creative_generator.text_client',return_value=(api,'fixture-model')), \
         patch('core.creative_generator.time.sleep'):
        result=ask_json(layout_contract(config['student_font_pt'],config['minimum_text_pt'],coherent=True),
            lambda raw:validate(raw,band),'Activity design 9',response_schema=design_schema(
                {'render_mode':'authored','mechanic':'word_problems'},config))
    return result,api


class MathRepairChainTests(unittest.TestCase):
    def test_reported_multinumber_sentence_changes_result_only(self):
        page=library_page();before=deepcopy(page)
        result=repair_declared_result(page,'1')
        q=result['exercise']['questions'][0]
        self.assertEqual(q['answer'],RIGHT)
        self.assertEqual(q['calculation'],before['exercise']['questions'][0]['calculation'])
        self.assertEqual(page,before)
        self.assertIn('all 6 branches',q['answer'])

    def test_ambiguous_or_different_quantities_are_not_rewritten(self):
        for answer in ('There are 342 priority requests across all 6 branches.',
                       'There are 342 standard requests and 6 priority requests.',
                       'There are at least 342 standard requests across all 6 branches.',
                       'There are 342 standard requests across all 7 branches.',
                       'The book will be ready for pickup on the following Monday.'):
            page=library_page();page['exercise']['questions'][0]['answer']=answer
            self.assertIsNone(repair_declared_result(page,'1'),answer)

    def test_nonnumeric_calculation_result_is_computed_without_changing_task(self):
        page=library_page();page['exercise']['questions'][0]['calculation']['answer']='1782 requests'
        before=deepcopy(page);result=repair_calculation_metadata(page,'1')
        self.assertEqual(Fraction(result['exercise']['questions'][0]['calculation']['answer']),1782)
        self.assertEqual(result['exercise']['questions'][0]['answer'],WRONG)
        self.assertEqual(result['html'],page['html']);self.assertEqual(page,before)
        page['exercise']['questions'][0]['calculation']['expression']='__import__("os")'
        self.assertIsNone(repair_calculation_metadata(page,'1'))

    def test_grade_failure_precedes_repairing_superseded_prose(self):
        for band in ('3rd-4th','5th-6th'):
            with self.assertRaisesRegex(ValueError,'arithmetic is below '+band):validate(weak_page(),band)

    def test_numeric_metadata_error_identifies_question(self):
        page=library_page();page['exercise']['questions'][0]['calculation']['answer']='Monday'
        with self.assertRaisesRegex(ValueError,'Question 1: calculation answer must be numeric'):
            validate(page,'5th-6th')

    def test_metadata_then_prose_recovery_needs_one_completion_in_both_grades(self):
        for band in ('3rd-4th','5th-6th'):
            page=library_page();page['exercise']['questions'][0]['calculation']['answer']='Monday';before=deepcopy(page)
            result,api=ask([page],band);q=result['exercise']['questions'][0]
            self.assertEqual(api.chat.completions.create.call_count,1)
            self.assertEqual(q['answer'],RIGHT);self.assertEqual(Fraction(q['calculation']['answer']),1782)
            self.assertEqual(q['prompt'],PROMPT);self.assertEqual(q['space_mm'],45)
            self.assertEqual(result['images'],page['images']);self.assertEqual(page,before)

    def test_grade_revision_and_reported_result_finish_in_two_completions(self):
        for band in ('3rd-4th','5th-6th'):
            raw=weak_page();correction=library_page();correction['images']=[];correction['html']='<p>Discarded layout drift</p>'
            correction['exercise']['questions'][0]['space_mm']=0
            before=deepcopy(raw);result,api=ask([raw,correction],band)
            self.assertEqual(api.chat.completions.create.call_count,2)
            self.assertEqual(result['exercise']['questions'][0]['answer'],RIGHT)
            self.assertEqual(result['exercise']['questions'][0]['space_mm'],45)
            self.assertEqual(result['images'],raw['images']);self.assertEqual(raw,before)
            schema=api.chat.completions.create.call_args_list[1].kwargs['response_format']['json_schema']['schema']
            self.assertIn('prompt',schema['properties']['exercise']['properties']['questions']['items']['required'])

    def test_ambiguous_prose_retry_has_frozen_verified_value_and_no_calculation_instructions(self):
        page=library_page();page['exercise']['questions'][0]['answer']='The standard requests have all been handled.'
        correction={'exercise':{'questions':[{'id':'1','answer':RIGHT,'calculation':{'expression':'1+1','answer':2},
            'prompt':'Unrelated task','space_mm':0}]},'images':[],'html':''}
        result,api=ask([page,correction],'5th-6th')
        self.assertEqual(api.chat.completions.create.call_count,2)
        q=result['exercise']['questions'][0]
        self.assertEqual(q['answer'],RIGHT);self.assertEqual(q['calculation'],page['exercise']['questions'][0]['calculation'])
        self.assertEqual(q['prompt'],PROMPT);self.assertEqual(q['space_mm'],45)
        message=api.chat.completions.create.call_args.kwargs['messages'][-1]['content']
        self.assertIn('Python has already verified the exact numeric result: 1782',message)
        self.assertNotIn('Correct ONLY exercise.questions[].calculation',message)
        schema=api.chat.completions.create.call_args.kwargs['response_format']['json_schema']['schema']
        self.assertEqual(set(schema['properties']['exercise']['properties']['questions']['items']['properties']),{'id','answer'})
