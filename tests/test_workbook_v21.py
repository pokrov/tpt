"""Offline V2.1 content and print regressions; no network/provider access."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pypdf import PdfReader

from core.workbook_v21 import draft, validate
from core.workbook_v21_pdf import build_pdf


class V21Tests(unittest.TestCase):
    def test_four_distinct_question_actions_and_canonical_keys(self):
        book=draft()
        self.assertEqual(book['profile'],'plant_reading_observation_v2_1')
        for reading in book['readings']:
            self.assertEqual([q['kind'] for q in reading['questions']][:2],['mcq','mcq'])
            self.assertEqual(reading['questions'][-1]['kind'],'short')
            self.assertEqual(len(reading['questions']),4)
            self.assertTrue(all(q['evidence'] in ' '.join(reading['paragraphs']) for q in reading['questions']))
        self.assertEqual(book['readings'][0]['questions'][2]['answer'],[3,1,2])
        self.assertEqual(book['readings'][2]['questions'][2]['answer'],[4,1,3,2])
        self.assertEqual(book['human_status'],'Draft')
        self.assertTrue(all(v=='Unverified' for v in book['rights'].values()))

    def test_source_change_and_bad_key_fail(self):
        book=draft();book['readings'][0]['paragraphs'][0]+=' More text.'
        with self.assertRaisesRegex(ValueError,'Passage changed'):validate(book)
        book=draft();book['readings'][0]['questions'][2]['answer']=[1,1,3]
        with self.assertRaisesRegex(ValueError,'permutation'):validate(book)
        book=draft();book['readings'][1]['questions'][0]['answer']='D'
        # A valid letter alone cannot prove semantics; the independent human gate remains required.
        self.assertEqual(validate(book)['human_status'],'Draft')

    def test_letter_pages_and_printed_key_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ('color','ink'):
                path=build_pdf(draft(),Path(tmp)/f'{mode}.pdf',print_mode=mode)
                pages=[p.extract_text() for p in PdfReader(path).pages]
                self.assertEqual(len(pages),18)
                self.assertIn('V2.1 DRAFT',pages[2])
                for student,key in ((3,14),(5,15),(7,16)):
                    self.assertEqual(pages[student].count('1. '),1)
                    self.assertIn('4. ',pages[student])
                    self.assertIn('4. ',pages[key])
                self.assertNotIn('Accept:', ' '.join(pages[2:14]))
                self.assertIn('PUBLICATION BLOCKED',pages[-1])


if __name__=='__main__':unittest.main()
