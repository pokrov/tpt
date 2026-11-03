"""Build separate V3.1 drafts from canonical V2.1 content without provider calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

from core.paths import BASE_DIR
from core.workbook_v21 import draft
from core.workbook_v2 import digest
from design.build_v31_workbook import build_pdf


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raster_record(assets: Path, name: str) -> dict:
    path = assets / name
    if name in {'bean-growth-cover-art.png', 'bean-anatomy-germination-art.png'}:
        origin = 'Generated for approved V3 prototype; see design/ASSET_PROVENANCE.md'
        method = 'AI raster generation from original project prompt'
        provider = 'Codex built-in imagegen; exact model/terms not recorded'
    elif name in {'v3-bean-plant.png', 'v3-life-cycle-sheet.png'}:
        origin = 'Generated for V3 with Codex built-in image-generation tool'
        method = 'AI raster generation'
        provider = 'Codex built-in image generation; exact model/terms not recorded'
    else:
        parent = ('bean-growth-cover-art.png' if name == 'bean-growth-cover-art-ink.png'
                  else 'bean-anatomy-germination-art.png' if name == 'bean-anatomy-germination-ink.png'
                  else 'v3-bean-plant.png' if name == 'v3-bean-plant-ink.png'
                  else 'v3-life-cycle-sheet.png')
        origin = f'Local derivative of {parent}'
        method = 'Pillow grayscale conversion or bounded crop'
        provider = 'Codex local image processing; parent origin applies'
    return {
        'path': str(path), 'sha256': sha(path), 'origin': origin,
        'creator_provider': provider, 'creation_method': method,
        'license_or_terms': None, 'commercial_use_evidence': None,
        'commercial_rights': 'Unverified', 'human_science_review': 'Required',
    }


def main() -> None:
    output = BASE_DIR / 'tmp' / 'workbook-v31-output'
    output.mkdir(parents=True, exist_ok=True)
    book = draft()
    files = {}
    for mode in ('color', 'ink'):
        path = output / f'how-plants-grow-v3.1-letter-{mode}.pdf'
        build_pdf(book, path, print_mode=mode)
        files[mode] = {'filename': path.name, 'sha256': sha(path), 'pages': 18}
    assets = BASE_DIR / 'design' / 'assets'
    asset_names = (
        'bean-growth-cover-art.png', 'bean-growth-cover-art-ink.png',
        'bean-anatomy-germination-art.png', 'bean-anatomy-germination-ink.png',
        'v3-bean-plant.png', 'v3-bean-plant-ink.png',
        'v3-life-cycle-sheet.png', 'v3-life-cycle-sheet-ink.png',
        *(f'v3-stage-{i}{suffix}.png' for i in range(1, 6)
          for suffix in ('', '-ink')),
        *(f'v31-stage-{i}{suffix}.png' for i in (4, 5)
          for suffix in ('', '-ink')),
    )
    font_names = sorted({str(font.get_object().get('/BaseFont')).lstrip('/')
                         for page in PdfReader(str(output / files['color']['filename'])).pages
                         for font in page['/Resources']['/Font'].values()})
    manifest = {
        'schema_version': '3.1', 'title': book['title'], 'status': 'Draft',
        'canonical_v21_sha256': digest(book), 'files': files,
        'review_gates': {'science': 'Unverified', 'answers': 'Pending human review',
                         'layout': 'Pending human review', 'commercial_rights': 'Unverified'},
        'assets': [raster_record(assets, name) for name in asset_names] + [
            {'path': f'PDF font: {font}', 'origin': 'Font referenced by generated PDF',
             'creator_provider': 'ReportLab/PDF base font environment',
             'creation_method': 'PDF font resource', 'license_or_terms': None,
             'commercial_use_evidence': None, 'commercial_rights': 'Unverified'}
            for font in font_names
        ] + [
            {'path': 'V2.1 canonical text', 'sha256': digest(book['readings']),
             'origin': 'offline editorial draft', 'creator_provider': 'Prior V2.1 project editorial work',
             'creation_method': 'Locally defined canonical text and questions',
             'license_or_terms': None, 'commercial_use_evidence': None, 'commercial_rights': 'Unverified'},
            {'path': 'design/build_v31_workbook.py', 'sha256': sha(BASE_DIR/'design'/'build_v31_workbook.py'),
             'origin': 'local rendering code', 'creator_provider': 'Codex implementation',
             'creation_method': 'Programmatic PDF diagrams and layout', 'license_or_terms': None,
             'commercial_use_evidence': None, 'commercial_rights': 'Unverified'},
        ],
    }
    (output / 'asset-provenance.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
