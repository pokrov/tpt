"""Real SDK serialization with a mocked Gemini endpoint; no provider quota or secrets."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

from core.activity_generator import ActivityGenerationError
from core.creative_generator import ask_json
from core.review_transport import compact_review_schema, REVIEW_JSON_CONTRACT
from core.workbook_review import review_schema, review_varied_pack, validate_review
from tests.test_agent_grounding import page, verdict, RIGHT


def nested_limits(schema, depth=0):
    count=0
    if isinstance(schema,dict):
        array=schema.get('type')=='array'
        if array and depth and any(k in schema for k in ('minItems','maxItems')):count+=1
        count+=sum(nested_limits(value,depth+int(array)) for value in schema.values())
    elif isinstance(schema,list):
        count+=sum(nested_limits(value,depth) for value in schema)
    return count


class ReviewTransportTests(unittest.TestCase):
    def schema(self):
        return review_schema([page(RIGHT)],require_claims=True)

    def response(self, *, independent=False, bad_evidence=False):
        raw=verdict(answer=RIGHT,supported=True)
        check=raw['pages'][0]['question_checks'][0]
        if independent:
            check.pop('answer_claims')
        else:
            for claim in check['answer_claims']:
                claim['evidence']=[{'evidence_id':'E404' if bad_evidence else 'E1'}]
        return raw

    def client_factory(self, handler):
        def create(provider):
            return OpenAI(api_key='offline-placeholder',
                base_url='https://generativelanguage.googleapis.com/v1beta/openai/',max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handler))), 'fixture-model'
        return create

    def completion(self, payload):
        return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':0,'model':'fixture-model',
            'choices':[{'index':0,'message':{'role':'assistant','content':json.dumps(payload)},'finish_reason':'stop'}]})

    def test_transport_has_no_nested_array_limits_and_preserves_all_required_fields(self):
        original=self.schema();before=deepcopy(original)
        self.assertGreater(nested_limits(original),0)
        transport=compact_review_schema(original)
        self.assertEqual(original,before)
        self.assertEqual(nested_limits(transport),0)
        self.assertEqual(transport['properties']['pages']['minItems'],1)
        check=transport['properties']['pages']['items']['properties']['question_checks']['items']
        self.assertIn('answer_claims',check['required'])
        claim=check['properties']['answer_claims']['items']
        self.assertEqual(set(claim['required']),{'claim_id','supported','evidence','reason'})
        self.assertEqual(set(claim['properties']['evidence']['items']['required']),{'evidence_id'})

    def run_pack(self, *, reject=0, bad_evidence=False):
        calls=[];review_count=0
        def handle(request):
            nonlocal review_count
            body=json.loads(request.content);calls.append(body)
            is_review=any('Compare the existing answer keys' in m['content'] for m in body['messages'])
            if is_review:
                review_count+=1
                if review_count<=reject:
                    return httpx.Response(400,json={'error':{'message':'Schema constraint is too complex','code':400}})
                return self.completion(self.response(bad_evidence=bad_evidence))
            return self.completion(self.response(independent=True))
        pack={'grade_band':'3rd-4th','pages':[page(RIGHT)]}
        repair=Mock(side_effect=AssertionError('An unsupported key must receive scoped content repair'))
        with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
             patch('core.creative_generator.text_client',side_effect=self.client_factory(handle)), \
             patch('core.creative_generator.time.sleep'):
            try:
                review_varied_pack(pack,ask_json,repair,require_claims=True)
            except Exception as exc:
                return pack,calls,repair,exc
        return pack,calls,repair,None

    def test_production_review_sends_compact_schema_to_real_sdk(self):
        pack,calls,repair,error=self.run_pack()
        self.assertIsNone(error)
        self.assertEqual(len(calls),2)
        schema=calls[-1]['response_format']['json_schema']['schema']
        self.assertEqual(nested_limits(schema),0)
        self.assertIn(REVIEW_JSON_CONTRACT,calls[-1]['messages'][1]['content'])
        self.assertEqual(pack['content_checks']['status'],'passed')
        repair.assert_not_called()

    def test_400_retries_only_review_once_in_json_mode_with_same_model_and_validator(self):
        pack,calls,repair,error=self.run_pack(reject=1)
        self.assertIsNone(error)
        self.assertEqual([c['response_format']['type'] for c in calls],['json_schema','json_schema','json_object'])
        self.assertEqual(calls[-1]['model'],calls[-2]['model'])
        self.assertEqual(calls[-1]['messages'],calls[-2]['messages'])
        self.assertEqual(pack['content_checks']['status'],'passed')
        repair.assert_not_called()

    def test_repeated_400_stops_after_one_fallback_without_restarting_the_pack(self):
        pack,calls,repair,error=self.run_pack(reject=2)
        self.assertIsInstance(error,ActivityGenerationError)
        self.assertIn('Workbook content review: gemini: HTTP 400',str(error))
        self.assertEqual(len(calls),3)
        self.assertNotIn('content_checks',pack)
        repair.assert_not_called()

    def test_json_mode_does_not_approve_fabricated_source_evidence(self):
        pack,calls,repair,error=self.run_pack(reject=1,bad_evidence=True)
        self.assertIsInstance(error,ActivityGenerationError)
        repair.assert_not_called()
        self.assertIn('unknown evidence_id',str(error))
        self.assertLessEqual(len(calls),6)
        self.assertNotIn('content_checks',pack)

    def test_python_still_enforces_page_question_claim_evidence_and_issue_bounds(self):
        for kind in ('pages','questions','claims','evidence','issues'):
            raw=self.response();record=raw['pages'][0];check=record['question_checks'][0]
            if kind=='pages':raw['pages']*=2
            elif kind=='questions':record['question_checks']*=2
            elif kind=='claims':check['answer_claims']*=7
            elif kind=='evidence':check['answer_claims'][0]['evidence']*=5
            else:record['issues']=['Issue']*7
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                validate_review(raw,[page(RIGHT)],require_claims=True)

    def test_auth_model_errors_and_other_stages_never_use_this_fallback(self):
        for status, opt_in in ((401,True),(404,True),(400,False)):
            calls=[]
            def handle(request):
                calls.append(json.loads(request.content))
                return httpx.Response(status,json={'error':{'message':'Rejected','code':status}})
            with patch('core.creative_generator.text_provider_names',return_value=['gemini']), \
                 patch('core.creative_generator.text_client',side_effect=self.client_factory(handle)), \
                 self.subTest(status=status,opt_in=opt_in),self.assertRaises(ActivityGenerationError):
                ask_json('Return JSON with reviewed pages.',lambda raw:raw,
                    'Workbook content review' if opt_in else 'Activity design 1',
                    response_schema=compact_review_schema(self.schema()),allow_schema_fallback=opt_in)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0]['response_format']['type'],'json_schema')
