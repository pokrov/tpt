"""Offline V2 acceptance checks; no configured provider is contacted."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from core.workbook_v2 import draft, validate, review_issues, digest
from core.workbook_v2_pdf import build_pdf
from core.workbook_v2_review import science_review, blind_answer_review
from core.workbook_v2_store import save_draft, load_draft, set_review


class WorkbookV2Tests(unittest.TestCase):
    def test_false_taxonomy_and_source_change_block(self):
        book=draft()
        book['readings'][0]['paragraphs'][0]+=' All non-flowering plants produce spores.'
        with self.assertRaisesRegex(ValueError,'Passage changed'):validate(book)
        from core.workbook_v2 import digest
        book['readings'][0]['source_hash']=digest(book['readings'][0]['paragraphs'])
        for question in book['readings'][0]['questions']:
            question['source_hash']=book['readings'][0]['source_hash']
        with self.assertRaisesRegex(ValueError,'misleading'):validate(book)

    def test_question_order_and_evidence(self):
        book=draft();book['readings'][0]['questions'][0]['answer']='Z'
        with self.assertRaisesRegex(ValueError,'four distinct options'):validate(book)
        book=draft();book['readings'][0]['questions'][0]['evidence']='Invented sentence.'
        with self.assertRaisesRegex(ValueError,'literal passage evidence'):validate(book)

    def test_reading_length_and_dependency_invalidation(self):
        book=draft()
        self.assertTrue(all(120<=len(' '.join(r['paragraphs']).split())<=180 for r in book['readings']))
        book['readings'][1]['paragraphs'][0]+=' A leaf can be observed.'
        with self.assertRaisesRegex(ValueError,'Passage changed'):validate(book)
        book['readings'][1]['source_hash']=digest(book['readings'][1]['paragraphs'])
        with self.assertRaisesRegex(ValueError,'literal passage evidence'):validate(book)

    def test_no_auto_approval_and_review_boundaries(self):
        book=draft()
        self.assertTrue(review_issues(book))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pdf=root/'book.pdf';pdf.write_bytes(b'%PDF-test')
            with patch('core.paths.OUTPUT_DIR',root):
                save_draft(book,pdf,root=root/'records')
                loaded,record=load_draft('book',root=root/'records')
                self.assertEqual(record['status'],'Draft')
                self.assertEqual(record['quality_score'],None)
                with self.assertRaisesRegex(ValueError,'verification'):
                    set_review('book',{'status':'Human approved'},root=root/'records')
                updated=set_review('book',{'scores':{'science':25,'education':25,'answers':20,'layout':15,'originality_rights':15}},root=root/'records')
                self.assertEqual(updated['quality_score'],100)
                self.assertNotEqual(updated['status'],'Human approved')
                with self.assertRaisesRegex(ValueError,'Retain every original'):
                    set_review('book',{'science_claims':[{'id':[],'reading_id':'seed'}]},root=root/'records')
                with self.assertRaisesRegex(ValueError,'Rights'):
                    set_review('book',{'rights_status':'Human verified'},root=root/'records')

    def test_mocked_semantic_review_has_no_approval(self):
        book=draft()
        def science_ask(prompt, validator, label, tokens):
            self.assertIn('non-flowering',prompt)
            return validator({'findings':[]})
        self.assertFalse(science_review(book,science_ask)['human_verified'])
        def blind_ask(prompt, validator, label, tokens):
            self.assertNotIn('"evidence"',prompt)
            reports=[]
            for reading in book['readings']:
                for q in reading['questions']:
                    reports.append(dict(question_id=q['id'],answer=q['answer'],supported=True,
                                        reason='Supported by source.',evidence_quote=q['evidence']))
            return validator({'reports':reports})
        result=blind_answer_review(book,blind_ask)
        self.assertEqual(result['status'],'Ready for human review')
        self.assertFalse(result['human_verified'])

    def test_human_approval_requires_complete_record(self):
        book=draft()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pdf=root/'book.pdf';pdf.write_bytes(b'%PDF-test')
            with patch('core.paths.OUTPUT_DIR',root):
                record=save_draft(book,pdf,root=root/'records')
                assets=copy.deepcopy(record['assets'])
                for asset in assets:
                    asset.update(commercial_status='Verified',terms_reference='Documented permission checked',
                                 reviewer_notes='Human checked the asset and terms.')
                claims=copy.deepcopy(record['science_claims'])
                for claim in claims:
                    claim.update(status='Verified',source_url='https://example.org/human-source',
                                 reviewer_notes='Human checked the cited source.')
                with self.assertRaisesRegex(ValueError,'Every passage'):
                    set_review('book',{'science_claims':claims[:-1]+[record['science_claims'][-1]],
                                       'science_status':'Human verified'},root=root/'records')
                approved=set_review('book',dict(assets=assets,science_claims=claims,science_status='Human verified',
                     rights_status='Human verified',answer_review='Human verified',layout_review='Human verified',
                     reviewer_notes='Human editor checked the completed workbook.',status='Human approved'),root=root/'records')
                self.assertEqual(approved['status'],'Human approved')
                self.assertEqual(approved['issues'],[])

    def test_letter_color_ink_and_original_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for mode in ('color','ink'):
                pdf=build_pdf(draft(),root/f'{mode}.pdf',print_mode=mode)
                reader=PdfReader(str(pdf))
                self.assertEqual(len(reader.pages),16)
                self.assertAlmostEqual(float(reader.pages[0].mediabox.width),612,places=1)
                self.assertIn('PUBLICATION BLOCKED',reader.pages[-1].extract_text())
                self.assertIn('Observation Log',reader.pages[10].extract_text())


if __name__=='__main__':unittest.main()
