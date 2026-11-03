"""Build a separate V2.1 candidate without reading credentials or using providers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.paths import BASE_DIR
from core.workbook_v21 import draft
from core.workbook_v21_pdf import build_pdf
from core.workbook_v2 import digest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output=BASE_DIR/'tmp'/'workbook-v21-output'
    output.mkdir(parents=True,exist_ok=True)
    book=draft()
    files={}
    for mode in ('color','ink'):
        path=output/f'how-plants-grow-v2.1-letter-{mode}.pdf'
        build_pdf(book,path,print_mode=mode)
        files[mode]={'filename':path.name,'sha256':sha(path),'pages':18}
    logo=BASE_DIR/'assets'/'store-logo.png'
    renderer=BASE_DIR/'core'/'workbook_v21_pdf.py'
    manifest={
        'schema_version':'2.1','profile':book['profile'],'title':book['title'],
        'status':'Draft','canonical_sha256':digest(book),'files':files,
        'review_gates':{'science':'Unverified','answers':'Validation required','layout':'Validation required','commercial_rights':'Unverified'},
        'assets':[
            {'id':'cover-logo','sha256':sha(logo) if logo.is_file() else None,'source':'user supplied','rights':'Unverified','license_reference':None},
            {'id':'vector-diagrams','sha256':sha(renderer),'source':'locally authored rendering code','rights':'Unverified','license_reference':None},
            {'id':'passages-and-questions','sha256':digest(book['readings']),'source':'offline editorial draft','rights':'Unverified','license_reference':None},
            {'id':'font','source':'local renderer; exact installed font requires review','rights':'Unverified','license_reference':None},
        ],
    }
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(output)


if __name__=='__main__':main()
