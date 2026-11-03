"""Stable answer IDs replace brittle verbatim reconstruction without dropping coverage."""
from copy import deepcopy
import json
import re
import unittest

from core.answer_grounding import answer_unit_bank, claim_issues
from core.workbook_review import review_varied_pack
from tests.test_agent_grounding import page, verdict, SOURCE, RIGHT


class AnswerUnitTests(unittest.TestCase):
    def test_bank_is_deterministic_and_retains_every_answer_token_without_modifying_it(self):
        cases=[RIGHT, 'Accept any accurate paraphrase. Example: Volunteers prepare care packages.',
            '1. 12.5 metres; 2. 0.75 litres; 3. 1/4 kg.',
            'Dr. Lee works in the U.S. community. Citizens help after 11 a.m. today.',
            '1: C; 2: D; 3: B; 4: A',
            'First complete assertion. Second complete assertion. Third complete assertion. '
            'Fourth complete assertion. Fifth complete assertion. Sixth complete assertion. Seventh complete assertion.']
        for answer in cases:
            with self.subTest(answer=answer):
                before=answer;bank=answer_unit_bank(answer)
                self.assertEqual(bank,answer_unit_bank(answer))
                self.assertLessEqual(len(bank),6)
                self.assertEqual([u['id'] for u in bank],list(range(1,len(bank)+1)))
                tokens=lambda value:re.findall(r'\w+|[%$€£]',value)
                self.assertEqual(tokens(' '.join(u['text'] for u in bank)),tokens(answer))
                self.assertEqual(answer,before)

    def test_long_decimal_and_abbreviation_examples_do_not_make_orphan_units(self):
        self.assertEqual(len(answer_unit_bank('The result is 12.5 metres.')),1)
        bank=answer_unit_bank('Dr. Lee lives in the U.S. community. The return is 12.5 metres.')
        self.assertEqual(len(bank),2)
        self.assertTrue(bank[0]['text'].startswith('Dr. Lee'))

    def test_reordered_and_duplicate_positive_reviews_need_no_word_copy(self):
        answer='They organize food drives. They also prepare care packages.'
        raw=verdict(answer=answer,supported=True)
        check=raw['pages'][0]['question_checks'][0]
        check['answer_claims'].reverse()
        check['answer_claims'].append(deepcopy(check['answer_claims'][0]))
        check['answer_claims'][0]['claim_id']=str(check['answer_claims'][0]['claim_id'])
        self.assertEqual(claim_issues(check,page(answer)['exercise']['questions'][0],page(answer)),[])
        self.assertTrue(all('claim' not in c for c in check['answer_claims']))

    def test_missing_unknown_and_boolean_ids_fail_and_negative_duplicates_cannot_be_hidden(self):
        p=page('They organize food drives. They also prepare care packages.')
        check=verdict(answer=p['exercise']['questions'][0]['answer'],supported=True)['pages'][0]['question_checks'][0]
        for change in ('missing','unknown','boolean','no_id'):
            bad=deepcopy(check)
            if change=='missing':bad['answer_claims'].pop()
            elif change=='unknown':bad['answer_claims'][0]['claim_id']=99
            elif change=='boolean':bad['answer_claims'][0]['claim_id']=True
            else:bad['answer_claims'][0].pop('claim_id')
            with self.subTest(change=change),self.assertRaises(ValueError):
                claim_issues(bad,p['exercise']['questions'][0],p)
        negative=deepcopy(check['answer_claims'][0]);negative['supported']=False
        negative['reason']='This unit includes an unsupported assertion.'
        check['answer_claims'].append(negative)
        self.assertIn('unsupported',str(claim_issues(check,p['exercise']['questions'][0],p)))

    def test_source_quotes_are_still_required_and_cannot_be_fabricated(self):
        p=page(RIGHT);q=p['exercise']['questions'][0]
        for evidence in ([],[{'slot':'stimulus_a','quote':'Invented quoted evidence.'}]):
            check=verdict(answer=RIGHT,supported=True)['pages'][0]['question_checks'][0]
            check['answer_claims'][0]['evidence']=evidence
            self.assertTrue(claim_issues(check,q,p))

    def test_production_review_sees_banks_but_blind_solver_and_canonical_exercise_do_not(self):
        for band in ('3rd-4th','5th-6th'):
            pack={'grade_band':band,'pages':[page(RIGHT)]};before=deepcopy(pack['pages'][0]['exercise'])
            def ask(prompt,validate,label,*args,**kwargs):
                pages=json.loads(prompt.split('Activities:\n',1)[1])
                question=pages[0]['exercise']['questions'][0]
                raw=verdict(answer=RIGHT,supported=True)
                if label=='Workbook independent solutions':
                    self.assertNotIn('answer_units',question)
                    self.assertNotIn('answer',question)
                    raw['pages'][0]['question_checks'][0].pop('answer_claims')
                else:
                    self.assertEqual(question['answer_units'],answer_unit_bank(RIGHT))
                    self.assertIn('claim_id',kwargs['response_schema']['properties']['pages']['items']['properties']['question_checks']['items']['properties']['answer_claims']['items']['required'])
                    self.assertNotIn('copy every authored answer word',prompt)
                return validate(raw)
            review_varied_pack(pack,ask,lambda *args: self.fail('Valid source answer needs no repair'),require_claims=True)
            self.assertEqual(pack['pages'][0]['exercise'],before)
            self.assertEqual(pack['content_checks']['status'],'passed')
