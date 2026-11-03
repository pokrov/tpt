"""Exercise the local V2 route in an isolated test DATA_DIR only."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from base64 import b64encode


class WorkbookV2WebTests(unittest.TestCase):
    def test_offline_draft_and_dashboard(self):
        self.assertEqual(os.environ.get('LOCAL_SCHEDULER_THREAD'),'0')
        self.assertIn('workbook-v2-test',os.environ.get('DATA_DIR',''))
        from local_server import app
        from pypdf import PdfReader
        from core.paths import OUTPUT_DIR
        with app.test_client() as client:
            with patch.dict(os.environ,WEBHOOK_API_KEY='test-only-key'):
                self.assertEqual(client.get('/v2/plants/').status_code,401)
                password=b64encode(b'local:test-only-key').decode()
                self.assertEqual(client.get('/v2/plants/',headers={'Authorization':'Basic '+password}).status_code,200)
            home=client.get('/v2/plants/')
            self.assertEqual(home.status_code,200)
            self.assertIn(b'Plant Workbook V2',home.data)
            blocked=client.post('/v2/plants/draft',headers={'Origin':'http://evil.test'})
            self.assertEqual(blocked.status_code,403)
            response=client.post('/v2/plants/draft',headers={'Origin':'http://localhost'})
            self.assertEqual(response.status_code,201,response.data[:500])
            result=response.get_json()
            self.assertEqual(result['status'],'Draft')
            detail=client.get(result['review_url'])
            self.assertEqual(detail.status_code,200)
            self.assertIn(b'Publication blockers',detail.data)
            pdf=next(OUTPUT_DIR.glob('*plant-v2-draft.pdf'))
            self.assertEqual(len(PdfReader(str(pdf)).pages),16)
            ink=client.get(result['review_url']+'/ink')
            self.assertEqual(ink.status_code,200)
            ink.close()
            review=client.post(result['review_url']+'/review',json={'status':'Human approved'},headers={'Origin':'http://localhost'})
            self.assertEqual(review.status_code,400)
            self.assertIn(b'human verification',review.data.lower())
            self.assertEqual(client.get('/books').status_code,200)


if __name__=='__main__':unittest.main()
