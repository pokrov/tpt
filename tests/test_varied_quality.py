"""Regression cases for conflicting prompts and falsely approved math solutions."""
from copy import deepcopy
from fractions import Fraction
import json
import unittest
from unittest.mock import patch

from core.varied_generator import generate_varied_pack
from core.pipeline import load_grade_config
from core.varied_math_review import single_numeric_solution, independent_math_issues
from core.workbook_review import review_varied_pack
from tests.test_book_types import mixed_ask, mixed_plan


class WrittenPromptTests(unittest.TestCase):
    def test_real_varied_planner_has_no_positive_craft_or_picture_puzzle_guidance(self):
        class Captured(Exception):
            pass
        for band in ('3rd-4th','5th-6th'):
            def capture(prompt, *args, **kwargs):
                for forbidden in ('Include creative making, drawing', 'A single drawing, craft or maze',
                                  'hands-on responses when useful', 'render_mode is exact or authored',
                                  'face-drawing task needs'):
                    self.assertNotIn(forbidden,prompt)
                for required in ('All use render_mode="authored"', 'reading', 'mathematics',
                                 'one or two focused questions', 'No drawing', 'Exact requested title'):
                    self.assertIn(required,prompt)
                raise Captured()
            with patch('core.creative_generator.ask_json',side_effect=capture),self.assertRaises(Captured):
                generate_varied_pack('Garden',band,load_grade_config(),book_title='Garden')

    def test_page_authorship_also_uses_written_quality_guidance(self):
        class Captured(Exception):
            pass
        def capture(prompt, validate, label, *args, **kwargs):
            if label == 'Creative plan':
                return validate(mixed_plan())
            if label == 'Cover design':
                return mixed_ask(prompt,validate,label,*args,**kwargs)
            self.assertIn('Written workbook quality',prompt)
            self.assertNotIn('Include creative making, drawing',prompt)
            self.assertNotIn('A single drawing, craft or maze',prompt)
            raise Captured()
        with patch('core.creative_generator.ask_json',side_effect=capture), \
             patch('core.creative_generator.text_worker_limit',return_value=1),self.assertRaises(Captured):
            generate_varied_pack('Garden','3rd-4th',load_grade_config())


class IndependentMathTests(unittest.TestCase):
    def test_exact_numeric_results_allow_units_fractions_and_decimal_equivalence(self):
        for text, expected in [('58 seeds remain.',58), ('$1,250.50',Fraction('1250.50')),
                               ('3/4 of a litre',Fraction(3,4)), ('0.75 litres',Fraction(3,4)),
                               ('1 1/2 metres',Fraction(3,2)), ('−2.5 degrees',Fraction('-2.5'))]:
            self.assertEqual(single_numeric_solution(text),expected)
        for text in ['Compute 4 * 24 - 38 = 58.', 'No unique solution.', '75%', '9:30 am', '1/0']:
            self.assertIsNone(single_numeric_solution(text))

    def test_both_grade_bands_cannot_approve_conflicting_numeric_solutions(self):
        for band, expression, answer in [('3rd-4th','4*24-38',58), ('5th-6th','48*12',576)]:
            page={'title':'Math in Context','html':f'<p>Calculate {expression}.</p>',
                'exercise':{'render_mode':'authored','mechanic':'applied_math','directions':'Solve.',
                    'questions':[{'id':'1','prompt':f'Calculate {expression}.','answer':str(answer),
                                  'calculation':{'expression':expression,'answer':answer}}]},
                'answers':str(answer)}
            pack={'grade_band':band,'pages':[page]}
            calls=[]
            def ask(prompt,validate,label,*args,**kwargs):
                pages=json.loads(prompt.split('Activities:\n',1)[1]);calls.append(label)
                return validate({'pages':[{'page_number':p['page_number'],'source_accuracy':True,
                    'no_answer_leak':True,'reason':'Model incorrectly approves the conflicting result.',
                    'issues':[],'question_checks':[{'id':'1','source_support':True,'skill_match':True,
                        'grade_match':True,'answer_correct':True,'solution':str(answer-1)+' items.',
                        'reason':'An independent computation.'}]} for p in pages]})
            with self.subTest(band=band), self.assertRaisesRegex(ValueError,'independent solution gives'):
                review_varied_pack(pack,ask,lambda n,p,issues:deepcopy(p))
            self.assertEqual(len(calls),4)  # One repair and one recheck, no endless retry.
            self.assertNotIn('content_checks',pack)

    def test_explicit_rounding_and_nonmath_questions_are_preserved(self):
        page={'exercise':{'questions':[{'id':'1','prompt':'Divide 10 by 3. Round to one decimal place.',
            'calculation':{'expression':'10/3','answer':'3.3'}},{'id':'2','prompt':'Name two ideas.'}]}}
        review={'question_checks':[{'id':'1','solution':'3.3 metres.'},{'id':'2','solution':'2 examples.'}]}
        self.assertEqual(independent_math_issues(page,review),[])
