"""Matching pair coverage and bounded provenance-only review corrections."""
from copy import deepcopy
import json
import os
import re
import unittest
from unittest.mock import Mock,patch
import httpx
from core.answer_grounding import answer_unit_bank,evidence_bank,claim_issues
from core.answer_evidence import evidence_contract
from core.matching_grounding import independent_matching_issues
from core.review_format import prepare_review,ReviewFormatError
from core.workbook_review import validate_review,review_varied_pack
from core.creative_generator import ask_json
from core.activity_generator import ActivityGenerationError
import tests.test_review_transport as transport_fixture

KEY='1-B, 2-D, 3-A, 4-C'
TERMS=['Roots','Leaves','Stems','Flowers']
DEFINITIONS='A. Support leaves. B. Absorb water. C. Help produce seeds. D. Make food using light.'


def matching_page():
    return {'page_number':1,'title':'Plant Matching','html':'<p>'+DEFINITIONS+'</p><p>'+
        ' '.join(f'{i}. {term}' for i,term in enumerate(TERMS,1))+
        '</p><p>Garden tools include a spade and a watering can.</p><p>Match the numbered terms to definitions in Source A.</p>',
        'exercise':{'render_mode':'authored','mechanic':'text_matching','directions':'Read the lists and match.',
        'stimuli':[{'id':'definitions','label':'Source A','text':DEFINITIONS},
                   {'id':'other','label':'Source B','text':'Garden tools include a spade and a watering can.'}],
        'captions':[{'id':f'term_{i}','text':f'{i}. {term}'} for i,term in enumerate(TERMS,1)],
        'questions':[{'id':'1','prompt':'Match the numbered terms to definitions in Source A.','answer':KEY}]}}


def citation(page,slot):
    return {'evidence_id':next(e['id'] for e in evidence_bank(page) if e['slot']==slot)}


def response(page, *, independent=False,bad=False,solved=KEY):
    check={'id':'1','source_support':True,'skill_match':True,'answer_correct':True,'grade_match':True,
        'solution':solved,'reason':'The printed terms and definitions support these pairs.'}
    if not independent:
        check['answer_claims']=[{'claim_id':u['id'],'supported':True,'reason':'Both printed sides support this pair.',
            'evidence':[citation(page,'stimulus_definitions')]+[citation(page,'caption_term_'+n)
            for n in re.findall(r'([1-8])\s*[-:]\s*[A-H]',u['text'])]}
            for u in answer_unit_bank(page['exercise']['questions'][0]['answer'])]
        if bad:check['answer_claims'][0]['evidence']=[{'slot':'stimulus_definitions','quote':KEY}]
    return {'pages':[{'page_number':1,'source_accuracy':True,'no_answer_leak':True,
        'reason':'All matching information is printed.','issues':[],'question_checks':[check]}]}


class MatchingGroundingTests(unittest.TestCase):
    def test_matching_units_preserve_all_pairs_and_existing_evidence_bounds(self):
        for key in (KEY,'1-B; 2-D; 3-A; 4-C; 5-F; 6-E; 7-H; 8-G'):
            units=answer_unit_bank(key)
            self.assertLessEqual(len(units),6)
            self.assertEqual(re.findall(r'\w+',key),re.findall(r'\w+',' '.join(u['text'] for u in units)))
            self.assertTrue(all(len(re.findall(r'[1-8]\s*[-:]\s*[A-H]',u['text']))<=2 for u in units))
        self.assertEqual([u['text'] for u in answer_unit_bank(KEY)],KEY.split(', '))
        prose='The code is 1-B, 2-D, 3-A, 4-C.'
        self.assertEqual(answer_unit_bank(prose)[0]['text'],prose)

    def test_named_source_and_numbered_caption_givens_are_both_eligible(self):
        p=matching_page();before=deepcopy(p);q=p['exercise']['questions'][0]
        self.assertEqual(validate_review(response(p),[p],require_claims=True),{1:[]})
        contract=evidence_contract(q,p)
        self.assertEqual(contract['required_source_slots'],['stimulus_definitions'])
        self.assertIn(citation(p,'caption_term_1')['evidence_id'],contract['eligible_evidence_ids'])
        self.assertNotIn(citation(p,'stimulus_other')['evidence_id'],contract['eligible_evidence_ids'])
        self.assertEqual(p,before)

    def test_question_givens_must_be_explicit_complete_and_not_replace_named_source(self):
        p=matching_page();q=p['exercise']['questions'][0]
        q['prompt']+=' Terms: '+'; '.join(f'{i}. {t}' for i,t in enumerate(TERMS,1))
        audit=response(p)['pages'][0]['question_checks'][0]
        for c in audit['answer_claims']:c['evidence']=[citation(p,'question_1'),citation(p,'stimulus_definitions')]
        self.assertEqual(claim_issues(audit,q,p),[])
        audit['answer_claims'][0]['evidence']=[citation(p,'question_1')]
        self.assertIn('required sources',str(claim_issues(audit,q,p)))
        for labels in ('','1. Roots; 1. Roots; 1. Roots; 1. Roots','1. Roots; 2. Leaves; 3. Stems'):
            q['prompt']='Match terms to definitions in Source A: '+labels
            self.assertNotIn(citation(p,'question_1')['evidence_id'],evidence_contract(q,p)['eligible_evidence_ids'])

    def test_wrong_sources_and_nonmatching_questions_keep_source_restrictions(self):
        p=matching_page();q=p['exercise']['questions'][0];raw=response(p)
        raw['pages'][0]['question_checks'][0]['answer_claims'][0]['evidence']=[citation(p,'stimulus_other')]
        with self.assertRaisesRegex(ReviewFormatError,'does not permit'):validate_review(raw,[p],require_claims=True)
        q.update(prompt='According to Source A, what do roots do? 1. Roots; 2. Leaves; 3. Stems; 4. Flowers',answer='Roots absorb water.')
        self.assertNotIn(citation(p,'question_1')['evidence_id'],evidence_contract(q,p)['eligible_evidence_ids'])

    def test_bad_quote_is_an_audit_correction_target(self):
        p=matching_page()
        with self.assertRaises(ReviewFormatError) as caught:prepare_review(response(p,bad=True),[p])
        self.assertEqual(list(caught.exception.targets[0]['errors']),['evidence'])
        self.assertIn('absent from its printed source',str(caught.exception))

    def test_explicit_blind_matching_disagreement_is_mandatory(self):
        p=matching_page();before=deepcopy(p)
        blind=response(p,independent=True,solved='1-D, 2-B, 3-A, 4-C')['pages'][0]
        self.assertIn('matching key conflicts',str(independent_matching_issues(p,blind)))
        blind['question_checks'][0]['solution']='4-C, 2-D, 1-B, 3-A'
        self.assertEqual(independent_matching_issues(p,blind),[])
        self.assertEqual(p,before)


class MatchingCitationSDKTests(unittest.TestCase):
    def run_pack(self,band='3rd-4th', *, fallback=False,unsupported=False,repeat_bad=False,blind_wrong=False,known_negative=False):
        p=matching_page();pack={'grade_band':band,'pages':[deepcopy(p)]};calls=[];reviews=0
        fixture=transport_fixture.ReviewTransportTests()
        repair=Mock(side_effect=AssertionError('Only actual content defects may repair an activity'))
        def handle(request):
            nonlocal reviews
            body=json.loads(request.content);calls.append(body);text=body['messages'][-1]['content']
            if 'Correct REVIEW RESPONSE FORMAT ONLY' in text:
                fixed=deepcopy(response(p)['pages'][0]['question_checks'][0]['answer_claims'][0])
                if unsupported:fixed.update(supported=False,evidence=[],reason='The source cannot support this pairing.')
                elif repeat_bad:fixed['evidence']=[{'evidence_id':'E999'}]
                return fixture.completion({'corrections':[{'target_id':'R1','claim':fixed}]})
            if 'Compare the existing answer keys' in text:
                reviews+=1
                if fallback and reviews==1:return httpx.Response(400,json={'error':{'message':'Complex schema','code':400}})
                payload=response(p,bad=not blind_wrong)
                if known_negative:payload['pages'][0]['question_checks'][0]['answer_claims'][0]['supported']=False
                return fixture.completion(payload)
            return fixture.completion(response(p,independent=True,solved='1-D, 2-B, 3-A, 4-C' if blind_wrong else KEY))
        with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
             patch('core.creative_generator.text_client',side_effect=fixture.client_factory(handle)), \
             patch('core.creative_generator.time.sleep'),patch.dict(os.environ,{'DESIGN_VALIDATION_ATTEMPTS':'3'}):
            try:review_varied_pack(pack,ask_json,repair,require_claims=True)
            except Exception as error:return pack,calls,repair,error
        return pack,calls,repair,None

    def test_both_grades_correct_only_the_citation_without_blind_answer_leaks(self):
        for band in ('3rd-4th','5th-6th'):
            pack,calls,repair,error=self.run_pack(band)
            self.assertIsNone(error);self.assertEqual(len(calls),3)
            self.assertEqual(pack['pages'],[matching_page()]);self.assertEqual(pack['content_checks']['repair_rounds'],0)
            blind=json.loads(calls[0]['messages'][1]['content'].split('Activities:\n',1)[1])[0]['exercise']['questions'][0]
            self.assertNotIn('eligible_evidence_ids',blind);self.assertNotIn('answer',blind)
            review=json.loads(calls[1]['messages'][1]['content'].split('Activities:\n',1)[1])[0]['exercise']['questions'][0]
            self.assertEqual(len(review['answer_units']),4);self.assertIn('eligible_evidence_ids',review)
            repair.assert_not_called()

    def test_json_mode_recovers_with_same_validator(self):
        pack,calls,repair,error=self.run_pack(fallback=True)
        self.assertIsNone(error)
        self.assertEqual([r['response_format']['type'] for r in calls],['json_schema','json_schema','json_object','json_object'])
        repair.assert_not_called()

    def test_new_negative_verdict_enters_content_repair(self):
        for options in ({'unsupported':True},{'known_negative':True}):
            pack,calls,repair,error=self.run_pack(**options)
            self.assertIsInstance(error,AssertionError);self.assertIn('unsupported',str(repair.call_args.args[2]))
            self.assertNotIn('content_checks',pack)

    def test_repeated_bad_citation_exhausts_existing_budget_without_reauthoring(self):
        pack,calls,repair,error=self.run_pack(repeat_bad=True)
        self.assertIsInstance(error,ActivityGenerationError);self.assertEqual(len(calls),4)
        self.assertNotIn('content_checks',pack);repair.assert_not_called()

    def test_blind_matching_disagreement_enters_content_repair(self):
        pack,calls,repair,error=self.run_pack(blind_wrong=True)
        self.assertIsInstance(error,AssertionError);self.assertIn('matching key conflicts',str(repair.call_args.args[2]))
        self.assertNotIn('content_checks',pack)
