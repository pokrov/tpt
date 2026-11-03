"""PDF-bound canonical facts and library-to-listing workflows, entirely offline."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from listing_tool.product_info import write_product_info, read_product_info, info_path
from listing_tool.engine import draft_listing
from listing_server import create_app
from tests.test_listing_tool import fixture


def canonical_story(grade='3rd-4th'):
    units, pages = [], []
    for number in range(1,6):
        questions = [dict(prompt='What does this passage explain?',skill=skill,
                          answer='PRIVATE_SOLUTION',explanation='PRIVATE_KEY_EXPLANATION')
                     for skill in ('main_idea','detail','vocabulary','inference','cause_effect')]
        units.append(dict(title=f'Water Topic {number}',paragraphs=['Rain fills lakes and rivers. Water supports life.'],questions=questions))
        pages += [dict(title=f'Water Topic {number}',page_type='reading',reading_unit=number,images=[]),
                  dict(title=f'Water Topic {number} - QCM',page_type='qcm',reading_unit=number,images=[])]
    return dict(title='Water and Our World',theme='Water',grade_band=grade,book_type='reading_qcm',
                cover=dict(images=[]),reading_units=units,pages=pages,content_checks=dict(status='passed'))


class ProductInfoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root/'water.pdf'

    def test_final_canonical_counts_skills_and_no_answer_payload_both_grades(self):
        for band, grade in [('3rd-4th','3-4'),('5th-6th','5-6')]:
            fixture(self.pdf, grade)
            story = canonical_story(band)
            before = deepcopy(story)
            path = write_product_info(story,self.pdf,[1]*10)
            self.assertEqual(story,before)
            self.assertNotIn('PRIVATE_SOLUTION',path.read_text())
            self.assertNotIn('PRIVATE_KEY_EXPLANATION',path.read_text())
            book = read_product_info(self.pdf)
            self.assertEqual(book['metadata_source'],'agent')
            self.assertEqual(book['grade'],grade)
            self.assertEqual(book['suggested'],[2,3,4])
            self.assertEqual(sum(p['mcq'] for p in book['pages']),25)
            self.assertEqual(len(book['skill_refs']),25)
            listing = draft_listing(book)['listing']
            self.assertIn('5 reading passages and 25 multiple-choice questions',listing)
            self.assertIn('Identifying the main idea',listing)
            self.assertIn('Final-page answer key',listing)

    def test_stale_wrong_pdf_and_invalid_coverage_or_question_refs_rejected(self):
        fixture(self.pdf)
        path = write_product_info(canonical_story(),self.pdf,[1]*10)
        original = json.loads(path.read_text())
        mutations = [lambda d:d.update(pdf_sha256='0'*64),
                     lambda d:d['pages'].pop(),
                     lambda d:d['pages'][0].update(role='student'),
                     lambda d:d['skill_refs'][0].update(page=1),
                     lambda d:d['skill_refs'][0].update(question=99)]
        for mutate in mutations:
            data = deepcopy(original); mutate(data)
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                read_product_info(self.pdf)
        path.write_text(json.dumps(original))
        self.pdf.write_bytes(self.pdf.read_bytes()+b'\n')
        with self.assertRaises(ValueError):
            read_product_info(self.pdf)

    def test_legacy_native_cover_title_is_not_replaced_by_ocr_logo(self):
        from listing_tool.engine import inspect_pdf
        fixture(self.pdf)
        def extracted(reader,index,native):
            if index == 0:
                return dict(text='THE CLASSROOM\nGrades 5-6\nCOLLECTION',method='ocr',confidence=70,title='L_Y_] THE cLassroom')
            return dict(text=native,method='text',confidence=None,title='')
        with patch('listing_tool.ocr.PageTextReader.read',extracted):
            book = inspect_pdf(self.pdf)
        self.assertEqual(book['topic'],'Water and Our World')
        self.assertEqual(book['grade'],'3-4')

    def test_physical_continuation_positions_are_retained_without_duplicate_tasks(self):
        from reportlab.pdfgen.canvas import Canvas
        canvas = Canvas(str(self.pdf))
        for _ in range(6):
            canvas.drawString(40,700,'A physical worksheet page'); canvas.showPage()
        canvas.save()
        story = dict(title='Compare Water',grade_band='3rd-4th',book_type='varied_activities',
                     pages=[dict(title='Compare Sources',exercise=dict(questions=[dict(prompt='Compare the texts.')])) ,
                            dict(title='Sequence Steps',exercise=dict(questions=[dict(prompt='Order the steps.')]))])
        write_product_info(story,self.pdf,[2,2])
        book = read_product_info(self.pdf)
        self.assertEqual([p['number'] for p in book['pages'] if p['continuation']],[3,5])
        self.assertEqual(sum(p['question_count'] for p in book['pages']),2)
        text = draft_listing(book)['listing']
        self.assertEqual(text.count('• Compare Sources'),1)
        self.assertEqual(text.count('• Sequence Steps'),1)

    def test_pipeline_writes_sidecar_after_final_pdf_and_does_not_lose_pdf_if_metadata_fails(self):
        from core.pipeline import generate_book
        for fail in (False,True):
            story = canonical_story()
            with patch('core.pipeline.text_provider_names'),patch('core.pipeline.image_provider_name'), \
                 patch('core.pipeline.generate_activity_pack',return_value=story),patch('core.pipeline.generate_activity_images'), \
                 patch('core.pipeline.build_activity_pdf',side_effect=lambda story,config,path:fixture(path)), \
                 patch('listing_tool.product_info.write_product_info',wraps=write_product_info,
                       side_effect=OSError('Disk unavailable') if fail else None):
                result,pdf = generate_book(theme='Water',grade_band='3rd-4th',output_dir=self.root)
            self.assertTrue(pdf.exists())
            self.assertEqual(result['product_info_status'],'unavailable' if fail else 'saved')
            if not fail:
                self.assertEqual(read_product_info(pdf)['total'],12)


class ListingLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root/'library'; self.library.mkdir()
        self.pdf = self.library/'water.pdf'; fixture(self.pdf)
        self.app = create_app(self.root/'uploads', self.library)
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get('/listing-tool/')
        with self.client.session_transaction() as session:
            self.csrf = session['listing_csrf']

    def create(self):
        return self.client.post('/listing-tool/from-library/water.pdf',data={'csrf':self.csrf})

    def test_existing_library_book_needs_no_upload_and_creates_all_outputs(self):
        before = self.pdf.read_bytes()
        self.assertIn(b'water.pdf',self.client.get('/listing-tool/library').data)
        with patch('listing_tool.web.subprocess.run') as worker:
            self.assertEqual(self.client.get('/listing-tool/from-library/water.pdf').status_code,200)
            worker.assert_not_called()
        response = self.create()
        self.assertEqual(response.status_code,303,response.data)
        review = response.headers['Location']
        for kind in ('preview','title','listing'):
            with self.client.get(review+'/download/'+kind) as download:
                self.assertEqual(download.status_code,200)
        self.assertEqual(before,self.pdf.read_bytes())
        self.assertFalse(info_path(self.pdf).exists())

    def test_agent_metadata_used_without_ocr_and_bad_metadata_falls_back(self):
        path = write_product_info(canonical_story(),self.pdf,[1]*10)
        before = path.read_bytes()
        response = self.create()
        self.assertEqual(response.status_code,303,response.data)
        job = self.root/'uploads'/response.headers['Location'].rsplit('/',1)[1]
        book = json.loads((job/'book.json').read_text())
        self.assertEqual(book['metadata_source'],'agent')
        self.assertEqual(book['ocr_pages'],[])
        self.assertEqual(before,path.read_bytes())
        data = json.loads(before); data['pdf_sha256']='0'*64; path.write_text(json.dumps(data))
        response = self.create()
        self.assertEqual(response.status_code,303,response.data)
        job = self.root/'uploads'/response.headers['Location'].rsplit('/',1)[1]
        book = json.loads((job/'book.json').read_text())
        self.assertIn('did not match',book['metadata_note'])
        self.assertNotEqual(book.get('metadata_source'),'agent')

    def test_missing_paths_traversal_csrf_and_library_links(self):
        for name in ('missing.pdf','state.json','..%5Csecret.pdf'):
            self.assertEqual(self.client.get('/listing-tool/from-library/'+name).status_code,404)
        self.assertEqual(self.client.post('/listing-tool/from-library/water.pdf').status_code,403)
        outside = self.root/'outside.pdf'; fixture(outside)
        try:
            (self.library/'linked.pdf').symlink_to(outside)
        except OSError:
            pass
        else:
            self.assertEqual(self.client.get('/listing-tool/from-library/linked.pdf').status_code,404)

    def test_generation_result_and_existing_library_offer_listing_action(self):
        import webhook_server as web
        records=[dict(title='Water',filename='water.pdf',grade_band='3rd-4th',generated_on='2026-10-27',available=True)]
        with patch.object(web,'list_books',return_value=records):
            page = web.app.test_client().get('/books').data
            self.assertIn(b'/listing-tool/from-library/water.pdf',page)
            self.assertIn(b'Next: Create preview, title',page)
        with patch.object(web,'_authorized',return_value=True), \
             patch.object(web,'generate_book',return_value=({'title':'Water'},self.pdf)),patch.object(web,'register_book'):
            response = web.app.test_client().post('/generate',json={'description':'Water','grade_band':'3rd-4th'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['listing_url'],'/listing-tool/from-library/water.pdf')
