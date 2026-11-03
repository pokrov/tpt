"""Regress the missing Statement header and its rejected layout-only repair."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.creative_generator import ask_json, layout_contract, merge_layout_repair
from core.table_captions import prepare_table_captions, NEUTRAL_HEADERS
from tests.test_missing_table_headers import food_comparison_page
import tests.test_missing_table_headers as header_fixtures


class StatementHeaderTests(unittest.TestCase):
    def test_missing_statement_header_binds_locally_in_both_grades_in_one_completion(self):
        for band in ('3rd-4th','5th-6th'):
            raw=food_comparison_page('th_statement');before=deepcopy(raw)
            api=Mock();api.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(raw)),finish_reason='stop')])
            with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
                 patch('core.creative_generator.text_client',return_value=(api,'fixture-model')):
                result=ask_json(layout_contract(12,12,coherent=True),lambda value:header_fixtures.MissingTableHeaderTests().validate(value,band),'Activity design 4')
            self.assertEqual(api.chat.completions.create.call_count,1)
            self.assertIn({'id':'th_statement','text':'Statement'},result['exercise']['captions'])
            for key,value in before['exercise'].items():
                self.assertEqual(result['exercise'][key],value)
            self.assertEqual(result['images'],before['images'])
            self.assertEqual(result['html'].count('height:35mm'),2)
            self.assertEqual(raw,before)

    def test_layout_only_repair_can_supply_same_heading_without_changing_task_or_art(self):
        for band in ('3rd-4th','5th-6th'):
            raw=food_comparison_page('th_statement');before=deepcopy(raw)
            correction={'html':raw['html'],'exercise':{'captions':[{'id':'th_statement','text':'Statement'}],
                'questions':[{'id':'1','prompt':'Drifted task','answer':'Wrong','space_mm':0}]},'images':[]}
            result=header_fixtures.MissingTableHeaderTests().validate(merge_layout_repair(raw,correction),band)
            self.assertEqual(result['exercise']['questions'],before['exercise']['questions'])
            self.assertEqual(result['exercise']['stimuli'],before['exercise']['stimuli'])
            self.assertEqual(result['images'],before['images'])
            self.assertIn({'id':'th_statement','text':'Statement'},result['exercise']['captions'])
            self.assertEqual(raw,before)

    def test_heading_does_not_infer_data_facts_answers_or_conflicting_prefills(self):
        for markup in ('<table><tr><td data-content="caption_th_statement"></td></tr></table>',
                       '<p data-content="caption_th_statement"></p>',
                       '<th data-content="caption_th_statement"></th>',
                       '<table><tr><th data-content="caption_th_statement"><img data-asset="scene"/></th></tr></table>',
                       '<table><tr><th data-content="caption_th_statement">Families gather at noon.</th></tr></table>'):
            raw={'html':markup,'exercise':{'render_mode':'authored','captions':[]}}
            prepare_table_captions(raw)
            self.assertNotIn({'id':'th_statement','text':'Statement'},raw['exercise']['captions'])
        original=food_comparison_page('th_statement')
        for text in ('Families gather at noon.','Correct answer: A','Write your statement.'):
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,'already printed'):
                merge_layout_repair(original,{'html':original['html'],'exercise':{'captions':[{'id':'th_statement','text':text}]}})

    def test_existing_wording_and_idempotence_remain_authoritative(self):
        raw=food_comparison_page('th_statement')
        raw['exercise']['captions']=[{'id':'th_statement','text':'Original heading'}]
        prepare_table_captions(raw)
        self.assertEqual(raw['exercise']['captions'][0]['text'],'Original heading')
        first=deepcopy(raw);prepare_table_captions(raw);self.assertEqual(raw,first)

    def test_layout_retry_lists_exactly_the_shared_neutral_headings(self):
        original=food_comparison_page('heading_x')
        correction={'html':original['html'],'exercise':{'captions':[{'id':'heading_x','text':'Statement'}]}}
        api=Mock();api.chat.completions.create.side_effect=[SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(raw)),finish_reason='stop')]) for raw in (original,correction)]
        with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
             patch('core.creative_generator.text_client',return_value=(api,'fixture-model')), \
             patch('core.creative_generator.time.sleep'):
            result=ask_json(layout_contract(12,12,coherent=True),lambda raw:header_fixtures.MissingTableHeaderTests().validate(raw,'3rd-4th'),'Activity design 4')
        self.assertEqual(api.chat.completions.create.call_count,2)
        self.assertIn(', '.join(NEUTRAL_HEADERS.values()),api.chat.completions.create.call_args.kwargs['messages'][-1]['content'])
        self.assertEqual(result['exercise']['questions'],original['exercise']['questions'])
