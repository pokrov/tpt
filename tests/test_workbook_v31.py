"""Offline regression checks for the separate V3.1 draft renderer."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from core.workbook_v21 import draft
from design.build_v31_workbook import ASSETS, build_pdf


class V31WorkbookTests(unittest.TestCase):
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
                        self.assertIn(' '.join(q['prompt'].split()),
                                      ' '.join(key_page.split()))
                        if q['kind'] == 'mcq':
                            self.assertNotIn('CORRECT ANSWER', question_page)
                            self.assertIn(f'({q["answer"]}) {q["options"][q["answer"]]}', key_page)
                        elif isinstance(q['answer'], str):
                            self.assertIn(' '.join(q['answer'].split()),
                                          ' '.join(key_page.split()))
                        else:
                            for item, value in zip(q['items'], q['answer']):
                                self.assertIn(f'{item}: {value}', ' '.join(key_page.split()))
                    for paragraph in reading['paragraphs']:
                        self.assertIn(' '.join(paragraph.split()),
                                      ' '.join(pages[2 + index*2].split()))
                self.assertIn('PUBLICATION BLOCKED', pages[-1])
                self.assertIn('A seed begins to germinate when it takes in water', pages[14])
                self.assertIn('from sun / dashed energy arrow', pages[4])
                self.assertIn('xylem inside carries water', pages[6])
                for page in pages[10:12]:
                    for field in ('Moisture/condition:', 'Root:', 'Shoot:', 'Leaves:', 'Height:',
                                  'Notes:', 'Quick sketch'):
                        self.assertIn(field, page)

    def test_required_original_art_exists(self):
        for name in ('v3-bean-plant.png', 'v3-bean-plant-ink.png',
                     *(f'v3-stage-{i}.png' for i in range(1, 6)),
                     *(f'v31-stage-{i}.png' for i in (4, 5))):
            self.assertTrue((ASSETS / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
