"""Resolve accidentally serialized source formatting using declared content only."""
import html
import re

from core.content_binding import CanonicalTextContainers, canonical_content_slot

TAG_TEXT = re.compile(r'<\s*/?\s*[a-z][a-z0-9:-]*\b[^>]*>', re.I)


def decoded_markup(value):
    if not isinstance(value, str):
        return None
    candidate = value
    for _ in range(3):
        if TAG_TEXT.search(candidate):
            return candidate
        decoded = html.unescape(candidate)
        if decoded == candidate:
            break
        candidate = decoded
    return None


def normalize_plain_content(exercise):
    """Flatten harmless inline formatting and explicit known references, never invent facts.

    Reject unknown/cyclic references, media and conflicting prefills. Existing
    canonical source deduplication handles complete repeated source copies later.
    """
    fields = {}
    for kind, prefix in (('captions', 'caption_'), ('stimuli', 'stimulus_')):
        for record in exercise.get(kind, []) if isinstance(exercise.get(kind, []), list) else []:
            if isinstance(record, dict) and isinstance(record.get('id'), str) and isinstance(record.get('text'), str):
                key = prefix + record['id']
                if key in fields:
                    raise ValueError('Duplicate content IDs cannot resolve serialized source markup')
                fields[key] = (record, 'text')
    for key in ('passage', 'directions'):
        if isinstance(exercise.get(key), str):
            fields[key] = (exercise, key)
    original = {key: record[field] for key, (record, field) in fields.items()}
    resolved = {}

    def resolve(key, trail=()):
        if key in trail or len(trail) >= 8:
            raise ValueError('Source markup has cyclic content references; supply complete plain source text')
        if key in resolved:
            return resolved[key]
        value = original[key]
        markup = decoded_markup(value)
        if markup is None:
            return value
        parser = CanonicalTextContainers({})
        parser.feed(markup); parser.close()
        if parser.stack:
            raise ValueError('Source markup must be balanced; supply complete plain source text')

        def words(node):
            if isinstance(node, str):
                return node
            if 'comment' in node or node['tag'] not in {'span','strong','b','em','i','br','p','div','section'}:
                raise ValueError('Source text contains unsupported markup; supply plain source text without media or scripts')
            attrs = dict(node['attrs'])
            if len(attrs) != len(node['attrs']) or set(attrs) - {'data-content'}:
                raise ValueError('Source text contains layout attributes; keep layout outside the plain source text')
            slot = attrs.get('data-content')
            if slot is not None:
                slot = canonical_content_slot(slot, original)
                if slot not in original:
                    raise ValueError('Source markup references undeclared content; retain complete source text and declare every slot')
                expected = resolve(slot, trail + (key,))
                prefill = ''.join(words(child) for child in node['children']).strip()
                if prefill and ' '.join(prefill.split()) != ' '.join(expected.split()):
                    raise ValueError('Source markup has conflicting prefilled wording; preserve and reconcile both source texts')
                return expected
            text = ''.join(words(child) for child in node['children'])
            return text + ('\n' if node['tag'] in {'br','p','div','section'} else '')

        value = ''.join(words(node) for node in parser.root).strip()
        if not value or decoded_markup(value) is not None:
            raise ValueError('Unresolved markup in source text; supply complete plain source text')
        resolved[key] = value
        return value

    updates = {key: resolve(key) for key in fields}
    for key, value in updates.items():
        record, field = fields[key]
        record[field] = value


def reject_printed_slot_markup(text):
    """A final boundary check: internal placeholders are never student wording."""
    markup = decoded_markup(text)
    if markup is not None and re.search(r'\bdata-(?:content|asset|visual)\s*=', markup, re.I):
        raise ValueError('Unresolved content-slot markup would print as student text; repair the source binding before PDF generation')
