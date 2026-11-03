"""Offline regression checks for the separate V3 draft renderer."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from core.workbook_v21 import draft
from design.build_v3_workbook import ASSETS, build_pdf


class V3WorkbookTests(unittest.TestCase):
    def test_color_and_ink_have_canonical_questions_and_18_letter_pages(self):
        book = draft()
        with tempfile.TemporaryDirectory() as directory:
            for mode in ('color', 'ink'):
                pdf = Path(directory) / f'{mode}.pdf'
                build_pdf(book, pdf, print_mode=mode)
                reader = PdfReader(str(pdf))
                self.assertEqual(len(reader.pages), 18)
                self.assertTrue(all(abs(float(p.mediabox.width)-612) < .1 and
                                    abs(float(p.mediabox.height)-792) < .1
                                    for p in reader.pages))
                pages = [p.extract_text() or '' for p in reader.pages]
                for index, reading in enumerate(book['readings']):
                    question_page = pages[3 + index*2]
                    key_page = pages[14 + index]
                    for q in reading['questions']:
                        self.assertIn(' '.join(q['prompt'].split()),
                                      ' '.join(question_page.split()))
                        if q['kind'] == 'mcq':
                            self.assertNotIn('Source:', question_page)
                            self.assertIn(str(q['answer']), key_page)
                    for paragraph in reading['paragraphs']:
                        self.assertIn(' '.join(paragraph.split()),
                                      ' '.join(pages[2 + index*2].split()))
                self.assertIn('PUBLICATION BLOCKED', pages[-1])

    def test_required_original_art_exists(self):
        for name in ('v3-bean-plant.png', 'v3-bean-plant-ink.png',
                     *(f'v3-stage-{i}.png' for i in range(1, 6))):
            self.assertTrue((ASSETS / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
