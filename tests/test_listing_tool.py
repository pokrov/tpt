"""Offline end-to-end coverage; real PDFs and real worker subprocesses, no AI."""
from io import BytesIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from listing_tool.engine import inspect_pdf, select_pages, draft_listing, make_preview


def fixture(path, grade='3-4', varied=False):
    pdf = Canvas(str(path), pagesize=A4)
    def page(lines):
        for i, line in enumerate(lines):
            pdf.setFont('Helvetica', 12)
            pdf.drawString(40, 800-i*22, line)
        pdf.showPage()
    page(['Water and Our World', f'Grades {grade}', '5 readings - 25 questions - Answer key'])
    for i in range(1, 6):
        if varied:
            page([f'Activity {i}: Compare Sources', 'Name: __________ Date: ______', 'Read both sources and compare the details.', 'Source A: Water flows into the river.', 'Source B: Rain fills the lake.', '1. How are the sources different?'])
            page([f'Activity {i}: Calculate', 'Name: ________', 'Calculate the sum: 12 + 8.', 'Explain your answer.'])
        else:
            page([f'READING {i} - INFORMATIONAL TEXT', f'Water Topic {i}', 'Name: _______', 'Read with a purpose', '1. Rain fills lakes and rivers. Water supports many forms of life.', '2. Communities protect their water.'])
            lines = [f'READING {i} - CHECK YOUR UNDERSTANDING', f'Water Topic {i}', 'Name: _______']
            for n in range(1, 6):
                lines += [f'{n}. What can you infer about water?', '(A) First choice', '(B) Second choice', '(C) Third choice', '(D) Fourth choice']
            # Fit all five answer sets on one real question page.
            for j, line in enumerate(lines):
                pdf.setFont('Helvetica', 11)
                pdf.drawString(40, 805-j*24, line)
            pdf.showPage()
    page(['Answer Key', 'Reading 1: 1. A - Rain fills rivers.', 'Reading 2: 1. B', 'Reading 3: 1. C'])
    pdf.save()


class ListingEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'book.pdf'

    def test_reading_facts_both_grades_and_no_cover_key_leaks(self):
        for grade in ('3-4', '5-6'):
            fixture(self.pdf, grade)
            book = inspect_pdf(self.pdf)
            self.assertEqual(book['grade'], grade)
            self.assertEqual(book['suggested'], [2, 3, 4])
            self.assertEqual(book['pages'][-1]['role'], 'answer key / teacher page')
            draft = draft_listing(book)
            self.assertIn('5 reading passages and 25 multiple-choice questions', draft['listing'])
            self.assertIn('Water Topic 5', draft['listing'])
            self.assertIn('Rain fills lakes and rivers.', draft['listing'])
            self.assertNotIn('Reading 1: 1. A', draft['listing'])
            self.assertIn('A4 portrait', draft['listing'])

    def test_varied_has_no_invented_reading_counts(self):
        fixture(self.pdf, varied=True)
        book = inspect_pdf(self.pdf)
        draft = draft_listing(book)
        self.assertNotIn('25 multiple-choice', draft['listing'])
        self.assertIn('Solving written mathematics', draft['listing'])
        self.assertEqual(select_pages(book), [2, 3, 4])

    def test_selection_validation(self):
        fixture(self.pdf)
        book = inspect_pdf(self.pdf)
        for invalid in ('1,2,3', '2,3,12', '2,2,3', '2,3', '2,3,99', '0,2,3', '2,3,4,5', 'x,2,3'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                select_pages(book, invalid)
        self.assertEqual(select_pages(book, '4, 2, 3'), [4, 2, 3])

    def test_real_preview_has_three_watermarked_pages_and_preserves_original(self):
        fixture(self.pdf)
        original = self.pdf.read_bytes()
        output = self.root / 'preview.pdf'
        make_preview(self.pdf, output, [2, 3, 4])
        preview = PdfReader(output)
        self.assertEqual(len(preview.pages), 3)
        for page in preview.pages:
            self.assertIn('PREVIEW', page.extract_text())
            self.assertNotIn('/Annots', page)
            self.assertAlmostEqual(float(page.mediabox.width), A4[0], places=1)
        self.assertNotIn('Answer Key', ''.join(p.extract_text() for p in preview.pages))
        self.assertEqual(original, self.pdf.read_bytes())

    def test_unclassified_pages_need_explicit_selection(self):
        fixture(self.pdf)
        book = inspect_pdf(self.pdf)
        book['suggested'] = []
        with self.assertRaises(ValueError):
            select_pages(book)

    def test_unknown_grade_requires_choice_and_only_active_bands(self):
        fixture(self.pdf, grade='unknown')
        book = inspect_pdf(self.pdf)
        for grade in ('', '1-2', '7-8'):
            with self.assertRaises(ValueError):
                draft_listing(book, grade=grade)
        self.assertIn('Grades 5', draft_listing(book, grade='5-6')['title'])

    def test_encrypted_and_unreadable_blank_pdf_rejected(self):
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        writer.write(self.pdf)
        with self.assertRaisesRegex(ValueError, 'No readable text'):
            inspect_pdf(self.pdf)
        writer.encrypt('secret')
        writer.write(self.pdf)
        with self.assertRaisesRegex(ValueError, 'Password-protected'):
            inspect_pdf(self.pdf)


class ListingWebTests(unittest.TestCase):
    def setUp(self):
        from listing_server import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root / 'uploads')
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get('/listing-tool/')
        with self.client.session_transaction() as session:
            self.csrf = session['listing_csrf']
        self.pdf = self.root / 'book.pdf'
        fixture(self.pdf)

    def upload(self):
        return self.client.post('/listing-tool/upload', data={'csrf': self.csrf,
            'pdf': (BytesIO(self.pdf.read_bytes()), '../../unsafe.pdf')})

    def test_upload_build_edit_and_download_real_subprocess(self):
        response = self.upload()
        self.assertEqual(response.status_code, 303)
        review = response.headers['Location']
        page = self.client.get(review)
        self.assertIn(b'Water and Our World', page.data)
        response = self.client.post(review, data={'csrf': self.csrf, 'topic': 'Water', 'grade': '3-4', 'pages': '2,3,4'})
        self.assertEqual(response.status_code, 303, response.data)
        preview = self.client.get(review + '/download/preview')
        self.assertEqual(preview.mimetype, 'application/pdf')
        self.assertEqual(len(PdfReader(BytesIO(preview.data)).pages), 3)
        with self.client.get(review + '/download/listing') as download:
            listing = download.data.decode()
        self.assertIn('25 multiple-choice', listing)
        response = self.client.post(review + '/save', data={'csrf': self.csrf, 'title': '<b>My title</b>', 'listing': 'My reviewed description'})
        self.assertEqual(response.status_code, 303)
        with self.client.get(review + '/download/listing') as download:
            self.assertEqual(download.data, b'My reviewed description')
        self.assertIn(b'&lt;b&gt;My title&lt;/b&gt;', self.client.get(review).data)
        self.assertEqual(self.client.get(review + '/download/original').status_code, 404)
        preview.close()

    def test_csrf_invalid_pdf_and_host_restrictions(self):
        self.assertEqual(self.client.post('/listing-tool/upload').status_code, 403)
        response = self.client.post('/listing-tool/upload', data={'csrf': self.csrf, 'pdf': (BytesIO(b'bad pdf'), 'test.pdf')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list((self.root / 'uploads').iterdir()), [])
        self.assertEqual(self.client.get('/listing-tool/', base_url='http://evil.example').status_code, 400)
        self.assertEqual(self.client.get('/listing-tool/../../state.json').status_code, 404)

    def test_authentication_uses_existing_access_key(self):
        with patch.dict('os.environ', {'WEBHOOK_API_KEY': 'test-key'}):
            self.assertEqual(self.client.get('/listing-tool/').status_code, 401)
            self.assertEqual(self.client.get('/listing-tool/', auth=('local', 'test-key')).status_code, 200)

    def test_failed_build_rejects_key_page(self):
        review = self.upload().headers['Location']
        response = self.client.post(review, data={'csrf': self.csrf, 'topic': 'Water', 'grade': '3-4', 'pages': '2,3,12'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(review + '/download/preview').status_code, 404)
