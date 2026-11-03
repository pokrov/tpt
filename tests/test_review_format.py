"""Malformed review fields get bounded corrections; valid audits remain pinned."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import Mock, patch

import httpx

from core.activity_generator import ActivityGenerationError
from core.creative_generator import ask_json
from core.review_format import prepare_review, merge_repair, ReviewFormatError
from core.workbook_review import validate_review, review_varied_pack
from tests.test_agent_grounding import page, verdict, RIGHT
import tests.test_review_transport as transport_fixture


def reviewed():
    raw=verdict(answer=RIGHT,supported=True)
    raw['pages'][0]['question_checks'][0]['answer_claims'][0]['evidence']=[{'evidence_id':'E1'}]
    return raw


def claim(raw):
    return raw['pages'][0]['question_checks'][0]['answer_claims'][0]


def invalid(raw):
    try:
        prepare_review(raw)
    except ReviewFormatError as error:
        return error
    raise AssertionError('Expected a precise review-format diagnostic')


def corrections(error, reason='The exact printed excerpt supports this unit.'):
    return {'corrections':[{'target_id':t['target_id'],'claim':{
        'claim_id':1,'supported':True,'evidence':[{'evidence_id':'E1'}],'reason':reason}}
        for t in error.targets]}


class ReviewFormatTests(unittest.TestCase):
    def test_overlong_reason_reports_exact_field_length_and_limit(self):
        raw=reviewed();claim(raw)['reason']='x'*251
        error=invalid(raw)
        self.assertIn('Activity 1 Question 2 answer_claims[0]',str(error))
        self.assertIn('reason has 251 characters; limit is 250',str(error))
        self.assertEqual(list(error.targets[0]['errors']),['reason'])
        self.assertNotIn('x'*20,str(error))

    def test_literal_boolean_single_evidence_and_whitespace_normalize_without_mutation(self):
        raw=reviewed();c=claim(raw)
        c.update(supported=' TRUE ',reason='Supported  \n by\t the source.',evidence={'evidence_id':'E1'})
        before=deepcopy(raw)
        self.assertEqual(validate_review(raw,[page(RIGHT)],require_claims=True),{1:[]})
        self.assertEqual(raw,before)
        c['supported']=' false '
        self.assertIn('unsupported',str(validate_review(raw,[page(RIGHT)],require_claims=True)))
        c['supported']='probably'
        self.assertEqual(list(invalid(raw).targets[0]['errors']),['supported'])

    def test_all_bad_claim_fields_are_collected_without_guessing(self):
        raw=reviewed();c=claim(raw)
        c.pop('claim_id');c['supported']=None;c['evidence']=None;c['reason']=' '
        raw['pages'][0]['question_checks'][0]['answer_claims'].append({'claim_id':2,'reason':'x'*270})
        error=invalid(raw)
        self.assertEqual(len(error.targets),2)
        self.assertEqual(set(error.targets[0]['errors']),{'claim_id','supported','evidence','reason'})
        self.assertEqual(claim(raw)['supported'],None)

    def test_reason_correction_cannot_replace_verdict_evidence_ids_or_other_reviews(self):
        raw=reviewed();claim(raw).update(supported=False,reason='x'*270)
        raw['pages'][0]['issues']=['A substantive concern must remain.']
        error=invalid(raw);proposed=corrections(error)
        proposed['corrections'][0]['claim'].update(claim_id=6,evidence=[{'evidence_id':'E999'}])
        fixed=merge_repair(error.response,error.targets,proposed)
        expected=deepcopy(raw);claim(expected)['reason']=proposed['corrections'][0]['claim']['reason']
        self.assertEqual(fixed,expected)
        self.assertIn('unsupported',str(validate_review(fixed,[page(RIGHT)],require_claims=True)))
        self.assertEqual(claim(raw)['reason'],'x'*270)

    def test_unknown_missing_duplicate_correction_targets_fail(self):
        raw=reviewed();claim(raw)['reason']='x'*270;error=invalid(raw)
        for malformed in ({'corrections':[]},{'corrections':[{'target_id':'R999','claim':{}}]},
                          {'corrections':[{'target_id':'R1','claim':{}}]},
                          {'corrections':corrections(error)['corrections']*2}):
            with self.subTest(raw=malformed),self.assertRaises(ValueError):
                merge_repair(error.response,error.targets,malformed)

    def test_correction_still_rejects_missing_evidence_and_invented_sources(self):
        for evidence in ([],[{'evidence_id':'E999'}]):
            raw=reviewed();claim(raw)['evidence']=None;error=invalid(raw)
            proposed=corrections(error);proposed['corrections'][0]['claim']['evidence']=evidence
            fixed=merge_repair(error.response,error.targets,proposed)
            with self.assertRaises(ReviewFormatError):validate_review(fixed,[page(RIGHT)],require_claims=True)


class ReviewFormatSDKTests(unittest.TestCase):
    def run_pack(self, band='3rd-4th', *, initial_400=False, bad_patch=False, negative=False):
        calls=[];format_calls=0;review_calls=0
        fixture=transport_fixture.ReviewTransportTests()
        original=reviewed();claim(original).update(reason='Detailed explanation. '*20,supported=not negative)
        error=invalid(original)
        repair=Mock(side_effect=AssertionError('Substantive issues must enter bounded content repair'))
        def handle(request):
            nonlocal format_calls,review_calls
            body=json.loads(request.content);calls.append(body)
            text=body['messages'][-1]['content']
            if 'Correct REVIEW RESPONSE FORMAT ONLY' in text:
                format_calls+=1
                patch_payload=corrections(error,reason='x'*270 if bad_patch else 'The printed source directly supports the unit.')
                return fixture.completion(patch_payload)
            if 'Compare the existing answer keys' in text:
                review_calls+=1
                if initial_400 and review_calls==1:
                    return httpx.Response(400,json={'error':{'message':'Complex schema','code':400}})
                return fixture.completion(original)
            return fixture.completion(fixture.response(independent=True))
        pack={'grade_band':band,'pages':[page(RIGHT)]}
        with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
             patch('core.creative_generator.text_client',side_effect=fixture.client_factory(handle)), \
             patch('core.creative_generator.time.sleep'), \
             patch.dict(os.environ,{'DESIGN_VALIDATION_ATTEMPTS':'3'}):
            try:
                review_varied_pack(pack,ask_json,repair,require_claims=True)
            except Exception as exc:
                return pack,calls,repair,exc,format_calls
        return pack,calls,repair,None,format_calls

    def test_both_grades_repair_metadata_only_and_keep_canonical_workbook_unchanged(self):
        for band in ('3rd-4th','5th-6th'):
            pack,calls,repair,error,count=self.run_pack(band)
            self.assertIsNone(error)
            self.assertEqual(count,1)
            self.assertEqual(len(calls),3)
            self.assertEqual(pack['pages'],[page(RIGHT)])
            self.assertEqual(pack['content_checks']['repair_rounds'],0)
            schema=calls[-1]['response_format']['json_schema']['schema']
            self.assertEqual(set(schema['properties']),{'corrections'})
            self.assertIn('Only fields listed in errors may change',calls[-1]['messages'][-1]['content'])
            self.assertNotIn('Correct only this unit and return complete JSON',calls[-1]['messages'][-1]['content'])
            repair.assert_not_called()

    def test_json_mode_uses_same_scoped_correction_and_validators_after_one_400(self):
        pack,calls,repair,error,count=self.run_pack(initial_400=True)
        self.assertIsNone(error)
        self.assertEqual([r['response_format']['type'] for r in calls],['json_schema','json_schema','json_object','json_object'])
        self.assertEqual(count,1)
        self.assertEqual(pack['content_checks']['status'],'passed')
        repair.assert_not_called()

    def test_bad_corrections_stop_within_existing_validation_budget(self):
        pack,calls,repair,error,count=self.run_pack(bad_patch=True)
        self.assertIsInstance(error,ActivityGenerationError)
        self.assertIn('reason has 270 characters; limit is 250',str(error))
        self.assertEqual(len(calls),4)  # Independent, original review, two bounded corrections.
        self.assertEqual(count,2)
        self.assertNotIn('content_checks',pack)
        repair.assert_not_called()

    def test_negative_audit_cannot_be_overridden_by_a_reason_correction(self):
        pack,calls,repair,error,count=self.run_pack(negative=True)
        self.assertIsInstance(error,AssertionError)
        self.assertIn('unsupported',str(repair.call_args.args[2]))
        self.assertNotIn('content_checks',pack)
        self.assertEqual(count,1)


if __name__=='__main__':
    unittest.main()
