"""Local page OCR. Rendering/OCR never replaces the uploaded PDF or its artwork."""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
import math
import os
import re
import shutil
import subprocess
import time


class PageTextReader:
    """Lazy PDFium renderer with bounded, English Tesseract OCR per scan page."""

    def __init__(self, path):
        self.path = str(path)
        self.document = None
        self.deadline = time.monotonic() + 240

    def close(self):
        if self.document is not None:
            self.document.close()

    def read(self, index, native):
        # Ordinary text-rich workbook pages stay on the existing extraction path.
        if sum(c.isalnum() for c in native) >= 600:
            return dict(text=native, method='text', confidence=None, title='')
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise ValueError('Offline OCR needs pypdfium2. Rebuild the listing app or install requirements-listing.txt.') from exc
        if self.document is None:
            self.document = pdfium.PdfDocument(self.path)
        page = self.document[index]
        try:
            width, height = page.get_size()
            area = max(width * height, 1)
            image_area = 0
            for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
                left, bottom, right, top = obj.get_bounds()
                image_area += max(0, min(width, right)-max(0, left)) * max(0, min(height, top)-max(0, bottom))
            if sum(c.isalnum() for c in native) >= 40 and image_area / area < .45:
                return dict(text=native, method='text', confidence=None, title='')
            if not shutil.which('tesseract'):
                raise ValueError('Offline OCR needs Tesseract with English language data. Rebuild the app, or install Tesseract locally and add it to PATH.')
            remaining = self.deadline - time.monotonic()
            if remaining < 1:
                raise ValueError('Offline OCR reached its four-minute limit. Split this PDF into smaller files and try again.')
            scale = min(3, 3300 / max(width, height, 1), math.sqrt(12_000_000 / area))
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil()
                try:
                    buffer = BytesIO()
                    image.save(buffer, format='PNG')
                finally:
                    image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
        env = dict(os.environ, OMP_THREAD_LIMIT='1')
        try:
            result = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'eng', '--psm', '3', 'tsv'],
                                    input=buffer.getvalue(), capture_output=True,
                                    timeout=min(25, remaining), env=env)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f'Offline OCR timed out on page {index+1}. Try a clearer or smaller scan.') from exc
        if result.returncode:
            raise ValueError(f'Offline OCR could not read page {index+1}. Check the scan and English OCR installation.')
        return parse_tsv(result.stdout.decode('utf-8', errors='replace'))


def parse_tsv(value):
    lines, scores = {}, []
    for row in csv.DictReader(StringIO(value), delimiter='\t', quoting=csv.QUOTE_NONE):
        word = (row.get('text') or '').strip()
        if row.get('level') != '5' or not word:
            continue
        key = tuple(row.get(name) for name in ('page_num', 'block_num', 'par_num', 'line_num'))
        line = lines.setdefault(key, dict(words=[], height=0))
        line['words'].append(word)
        line['height'] = max(line['height'], int(row.get('height', 0)))
        score = float(row.get('conf', '-1'))
        if score >= 0:
            scores.append(score)
    rendered = [(' '.join(line['words']), line['height']) for line in lines.values()]
    candidates = [(text, height) for text, height in rendered
                  if len(text) > 3 and not re.match(
                      r'^(?:grades?\b|the classroom|your classroom|\d+\s+(?:readings?|questions?))', text, re.I)]
    return dict(text='\n'.join(text for text, height in rendered), method='ocr',
                confidence=round(sum(scores)/len(scores), 1) if scores else 0,
                title=max(candidates, key=lambda item: item[1])[0] if candidates else '')
