"""Bounded subprocess entry point; never imports the workbook generator."""
import json
from pathlib import Path
import sys

from .engine import inspect_pdf, draft_listing, select_pages, make_preview


def main():
    action, directory = sys.argv[1:]
    root = Path(directory)
    try:
        if action == 'inspect':
            metadata = root / 'product.json'
            if metadata.exists():
                from .product_info import read_product_info
                try:
                    book = read_product_info(root / 'original.pdf', metadata)
                except (ValueError, OSError, TypeError, KeyError):
                    book = inspect_pdf(root / 'original.pdf')
                    book['metadata_note'] = 'Saved product information did not match this PDF. PDF extraction / offline OCR was used instead.'
            else:
                book = inspect_pdf(root / 'original.pdf')
            (root / 'book.json').write_text(json.dumps(book), encoding='utf-8')
        elif action == 'build':
            book = json.loads((root / 'book.json').read_text(encoding='utf-8'))
            options = json.loads((root / 'options.json').read_text(encoding='utf-8'))
            chosen = select_pages(book, options['pages'])
            result = draft_listing(book, options['topic'], options['grade'])
            result['selected'] = chosen
            make_preview(root / 'original.pdf', root / 'preview.pending.pdf', chosen)
            for name, value in [('listing.txt', result['listing']), ('title.txt', result['title'])]:
                staged = root / (name + '.pending')
                staged.write_text(value, encoding='utf-8')
                staged.replace(root / name)
            (root / 'preview.pending.pdf').replace(root / 'preview.pdf')
            (root / 'result.pending.json').write_text(json.dumps(result), encoding='utf-8')
            (root / 'result.pending.json').replace(root / 'result.json')
        else:
            raise ValueError('Unknown offline operation.')
    except ValueError as exc:
        print(json.dumps({'error': str(exc)}))
        return 1
    except Exception:
        print(json.dumps({'error': 'The PDF could not be processed. Use a valid, unlocked PDF with readable printed text.'}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
