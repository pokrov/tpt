"""Real image-only/hybrid PDFs, real offline OCR, and bounded failure cases."""
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pypdfium2 as pdfium
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from listing_tool.engine import inspect_pdf, select_pages, make_preview, draft_listing
from listing_tool.ocr import PageTextReader
from tests.test_listing_tool import fixture


def scan_fixture(source, target, hybrid=False):
    """Rasterize actual text pages; resulting scan has no invisible text layer."""
    document = pdfium.PdfDocument(str(source))
    canvas = Canvas(str(target), pagesize=A4)
    try:
        for index in (0, 1, 2, 3, 11):
            page = document[index]
            bitmap = page.render(scale=2.5)
            image = bitmap.to_pil()
            try:
                canvas.drawImage(ImageReader(image), 0, 0, width=A4[0], height=A4[1])
                if hybrid:
                    canvas.setFont('Helvetica', 8)
                    canvas.drawString(25, 12, 'Scanned classroom resource - this footer is selectable text.')
                canvas.showPage()
            finally:
                image.close()
                bitmap.close()
                page.close()
        canvas.save()
    finally:
        document.close()


class ListingOCRTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = self.root / 'text.pdf'
        self.scan = self.root / 'scan.pdf'

    def test_real_scans_both_grades_extract_and_preview_without_changing_images(self):
        for grade in ('3-4', '5-6'):
            with self.subTest(grade=grade):
                fixture(self.original, grade)
                scan_fixture(self.original, self.scan)
                self.assertTrue(all(not p.extract_text().strip() for p in PdfReader(self.scan).pages))
                before = self.scan.read_bytes()
                book = inspect_pdf(self.scan)
                self.assertEqual(book['ocr_pages'], [1, 2, 3, 4, 5])
                self.assertEqual(book['grade'], grade)
                self.assertIn('Water', book['topic'])
                self.assertEqual(select_pages(book), [2, 3, 4])
                self.assertEqual(book['pages'][-1]['role'], 'answer key / teacher page')
                with self.assertRaises(ValueError):
                    select_pages(book, '2,3,5')
                draft = draft_listing(book)
                self.assertTrue(any('OCR' in note for note in draft['notes']))
                target = self.root / f'preview-{grade}.pdf'
                make_preview(self.scan, target, [2, 3, 4])
                preview = PdfReader(target)
                self.assertEqual(len(preview.pages), 3)
                self.assertTrue(all('PREVIEW' in p.extract_text() for p in preview.pages))
                self.assertTrue(all(len(list(p.images)) >= 1 for p in preview.pages))
                self.assertEqual(self.scan.read_bytes(), before)

    def test_hybrid_footer_does_not_hide_scanned_body(self):
        fixture(self.original)
        scan_fixture(self.original, self.scan, hybrid=True)
        book = inspect_pdf(self.scan)
        self.assertEqual(book['ocr_pages'], [1, 2, 3, 4, 5])
        self.assertEqual(book['grade'], '3-4')
        self.assertIn('Rain fills', book['pages'][1]['text'])
        self.assertEqual(book['pages'][-1]['role'], 'answer key / teacher page')

    def test_text_pdf_does_not_invoke_tesseract(self):
        fixture(self.original)
        with patch('listing_tool.ocr.subprocess.run', side_effect=AssertionError('unexpected OCR')):
            book = inspect_pdf(self.original)
        self.assertEqual(book['ocr_pages'], [])

    def test_missing_ocr_and_page_timeout_are_clear_errors(self):
        fixture(self.original)
        scan_fixture(self.original, self.scan)
        with patch('listing_tool.ocr.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Tesseract'):
                inspect_pdf(self.scan)
        with patch('listing_tool.ocr.subprocess.run', side_effect=subprocess.TimeoutExpired('tesseract', 25)):
            with self.assertRaisesRegex(ValueError, 'timed out on page 1'):
                inspect_pdf(self.scan)

    def test_real_scan_upload_and_worker_build(self):
        from listing_server import create_app
        fixture(self.original)
        scan_fixture(self.original, self.scan)
        app = create_app(self.root / 'uploads')
        app.testing = True
        client = app.test_client()
        client.get('/listing-tool/')
        with client.session_transaction() as session:
            csrf = session['listing_csrf']
        response = client.post('/listing-tool/upload', data={'csrf': csrf,
            'pdf': (BytesIO(self.scan.read_bytes()), 'scanned-book.pdf')})
        self.assertEqual(response.status_code, 303, response.data)
        location = response.headers['Location']
        self.assertIn(b'Offline OCR read pages', client.get(location).data)
        response = client.post(location, data={'csrf': csrf, 'topic': 'Water', 'grade': '3-4', 'pages': '2,3,4'})
        self.assertEqual(response.status_code, 303, response.data)
        with client.get(location + '/download/preview') as download:
            self.assertEqual(len(PdfReader(BytesIO(download.data)).pages), 3)
