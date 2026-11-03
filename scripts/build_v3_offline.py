"""Build separate V3 drafts from canonical V2.1 content without provider calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.paths import BASE_DIR
from core.workbook_v21 import draft
from core.workbook_v2 import digest
from design.build_v3_workbook import build_pdf


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = BASE_DIR / 'tmp' / 'workbook-v3-output'
    output.mkdir(parents=True, exist_ok=True)
    book = draft()
    files = {}
    for mode in ('color', 'ink'):
        path = output / f'how-plants-grow-v3-letter-{mode}.pdf'
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
    )
    manifest = {
        'schema_version': '3.0', 'title': book['title'], 'status': 'Draft',
        'canonical_v21_sha256': digest(book), 'files': files,
        'review_gates': {'science': 'Unverified', 'answers': 'Pending human review',
                         'layout': 'Pending human review', 'commercial_rights': 'Unverified'},
        'assets': [
            {'path': str(assets / name), 'sha256': sha(assets / name),
             'origin': 'Codex built-in image generation or local grayscale/crop derivative' if name.startswith('v3-')
                       else 'approved V3 prototype asset',
             'commercial_rights': 'Unverified', 'human_science_review': 'Required'}
            for name in asset_names
        ] + [
            {'path': 'Helvetica / Times PDF base fonts', 'origin': 'ReportLab PDF base fonts',
             'commercial_rights': 'Unverified'},
            {'path': 'V2.1 canonical text', 'sha256': digest(book['readings']),
             'origin': 'offline editorial draft', 'commercial_rights': 'Unverified'},
        ],
    }
    (output / 'asset-provenance.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
