"""Canonical excerpts prevent invented review quotes without bypassing evidence checks."""
from copy import deepcopy
import json
import unittest

from core.answer_grounding import evidence_bank, source_records, normalized, claim_issues
from core.workbook_review import review_varied_pack
from tests.test_agent_grounding import page, verdict, RIGHT


def checked(evidence, *, supported=True):
    check=verdict(answer=RIGHT,supported=True)['pages'][0]['question_checks'][0]
    check['answer_claims'][0].update(evidence=evidence,supported=supported)
    return check


class EvidenceBankTests(unittest.TestCase):
    def test_bank_is_literal_bounded_deterministic_and_does_not_lose_source_text(self):
        p=page(RIGHT)
        p['exercise']['passage']='Families prepare a table. '*40
        p['exercise']['captions']=[{'id':'note','text':'A\nline with 240 flowers and 12.5 metres.'},
                                  {'id':'long','text':'x'*651}]
        before=deepcopy(p);bank=evidence_bank(p)
        self.assertEqual(p,before)
        self.assertEqual(bank,evidence_bank(p))
        self.assertEqual([entry['id'] for entry in bank],[f'E{i}' for i in range(1,len(bank)+1)])
        records=source_records(p)
        records['question_2']=p['exercise']['questions'][0]['prompt']
        for slot,text in records.items():
            excerpts=[entry['text'] for entry in bank if entry['slot']==slot]
            # Whitespace and splits in an oversized single token lose no characters.
            self.assertEqual(''.join(''.join(excerpts).split()),''.join(text.split()))
            for excerpt in excerpts:
                self.assertLessEqual(len(excerpt),300)
                self.assertIn(normalized(excerpt),normalized(text))

    def test_reconstructed_quote_is_rejected_but_selecting_real_excerpt_preserves_valid_paraphrase(self):
        p=page(RIGHT);q=p['exercise']['questions'][0]
        # A true paraphrase is a valid answer but is not an exact source quotation.
        legacy=checked([{'slot':'stimulus_a','quote':RIGHT}])
        self.assertIn('absent from its printed source',str(claim_issues(legacy,q,p)))
        self.assertEqual(claim_issues(checked([{'evidence_id':'E1'}]),q,p),[])
        self.assertEqual(q['answer'],RIGHT)

    def test_missing_unknown_or_malformed_ids_cannot_be_inferred_from_text_or_position(self):
        p=page(RIGHT);q=p['exercise']['questions'][0]
        for evidence in ([],[{'evidence_id':'E999'}],[{'evidence_id':True}],
                         [{'evidence_id':1}],[{'evidence_id':None}],
                         [{'evidence_id':'E1','quote':'Invented override.'}]):
            with self.subTest(evidence=evidence):
                try:
                    self.assertTrue(claim_issues(checked(evidence),q,p))
                except ValueError:
                    pass

    def test_exact_excerpt_from_wrong_source_or_question_is_still_rejected(self):
        p=page(RIGHT);q=p['exercise']['questions'][0]
        p['exercise']['stimuli'].append({'id':'b','label':'Source B','text':p['exercise']['stimuli'][0]['text']})
        for slot in ('stimulus_b','question_2'):
            evidence_id=next(entry['id'] for entry in evidence_bank(p) if entry['slot']==slot)
            self.assertTrue(claim_issues(checked([{'evidence_id':evidence_id}]),q,p))
        # Metadata supplied by a caller cannot replace canonical sources.
        p['evidence_bank']=[{'id':'E999','slot':'stimulus_a','text':RIGHT}]
        self.assertIn('unknown evidence_id',str(claim_issues(checked([{'evidence_id':'E999'}]),q,p)))

    def test_negative_verdict_and_missing_source_evidence_remain_failures(self):
        p=page(RIGHT);q=p['exercise']['questions'][0]
        self.assertIn('unsupported',str(claim_issues(checked([{'evidence_id':'E1'}],supported=False),q,p)))
        self.assertIn('no supporting printed-source evidence',str(claim_issues(checked([]),q,p)))

    def test_calculation_can_reference_question_givens_without_using_its_answer(self):
        p=page('60');q=p['exercise']['questions'][0]
        q.update(prompt='There are 4 trays of 15 loaves. How many loaves are there?',calculation={'expression':'4*15'})
        evidence_id=next(entry['id'] for entry in evidence_bank(p) if entry['slot']=='question_2')
        self.assertEqual(claim_issues(checked([{'evidence_id':evidence_id}]),q,p),[])
        self.assertNotIn('60',str(evidence_bank(p)))

    def test_both_bands_receive_exact_excerpts_without_mutating_blind_or_canonical_payloads(self):
        for band in ('3rd-4th','5th-6th'):
            pack={'grade_band':band,'pages':[page(RIGHT)]};before=deepcopy(pack)
            def ask(prompt,validate,label,*args,**kwargs):
                pages=json.loads(prompt.split('Activities:\n',1)[1])
                raw=verdict(answer=RIGHT,supported=True)
                if label=='Workbook independent solutions':
                    self.assertNotIn('evidence_bank',pages[0])
                    self.assertNotIn('answer',pages[0]['exercise']['questions'][0])
                    raw['pages'][0]['question_checks'][0].pop('answer_claims')
                else:
                    self.assertEqual(pages[0]['evidence_bank'],evidence_bank(before['pages'][0]))
                    self.assertIn('evidence [{evidence_id}]',prompt)
                    raw['pages'][0]['question_checks'][0]['answer_claims'][0]['evidence']=[{'evidence_id':'E1'}]
                return validate(raw)
            review_varied_pack(pack,ask,lambda *a:self.fail('Valid paraphrase needs no content repair'),require_claims=True)
            self.assertEqual(pack['pages'],before['pages'])
            self.assertEqual(pack['content_checks']['repair_rounds'],0)


if __name__=='__main__':
    unittest.main()
