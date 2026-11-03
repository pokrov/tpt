"""Reproduce the Veterans Day source box printing serialized internal HTML."""
from copy import deepcopy
import html
import unittest

from core.plain_content import normalize_plain_content, reject_printed_slot_markup
from core.creative_generator import validate_design
from core.creative_layout import fragment
from tests.test_student_workbook import evidence_page, workbook_config
from tests.test_reading_bindings import plain_text

SOURCE = ('The community ceremony begins on November 11. A volunteer recorded 36 visitors '
          'at the library. One visitor said it was the most enjoyable event of the year.')
WRAPPER = ('<strong><span data-content="caption_source_a_label"></span></strong><br>'
           '<span data-content="caption_source_a_text"></span>')


def exercise():
    return {'captions':[{'id':'source_a_label','text':'Source A'},
                        {'id':'source_a_text','text':SOURCE}],
            'stimuli':[{'id':'source_a','label':'Source A','text':WRAPPER}]}


class PlainSourceMarkupTests(unittest.TestCase):
    def test_raw_and_entity_encoded_wrappers_expand_only_declared_text(self):
        for encode in (lambda s:s,html.escape,lambda s:html.escape(html.escape(s))):
            spec=exercise();spec['stimuli'][0]['text']=encode(WRAPPER)
            normalize_plain_content(spec)
            self.assertEqual(spec['stimuli'][0]['text'],'Source A\n'+SOURCE)
            self.assertEqual(spec['captions'],exercise()['captions'])
            once=deepcopy(spec);normalize_plain_content(spec);self.assertEqual(spec,once)

    def test_unknown_cyclic_conflicting_or_unsafe_markup_never_becomes_a_source(self):
        for bad in ('<span data-content="caption_missing"></span>',
                    '<span data-content="stimulus_source_a"></span>',
                    '<span data-content="caption_source_a_text">Different evidence.</span>',
                    '<script>secret()</script>', '<img src="https://invalid/">',
                    '<strong style="display:none">Keep this evidence.</strong>'):
            spec=exercise();spec['stimuli'][0]['text']=bad;before=deepcopy(spec)
            with self.subTest(bad=bad),self.assertRaises(ValueError):normalize_plain_content(spec)
            self.assertEqual(spec,before)

    def test_inline_prose_and_ordinary_mathematical_symbols_are_lossless(self):
        for value,expected in [('<strong>Rainfall</strong> measured 12 mm.','Rainfall measured 12 mm.'),
                               ('Compare 3 < 5 and 8 > 6.','Compare 3 < 5 and 8 > 6.')]:
            spec={'stimuli':[{'id':'a','text':value}]};normalize_plain_content(spec)
            self.assertEqual(spec['stimuli'][0]['text'],expected)

    def test_renderer_refuses_literal_internal_slot_markup(self):
        for text in (WRAPPER,html.escape(WRAPPER)):
            with self.assertRaisesRegex(ValueError,'markup would print'):reject_printed_slot_markup(text)
        reject_printed_slot_markup('Use the values where 3 < 5.')

    def test_complete_source_and_questions_render_in_both_grade_bands(self):
        for band in ('3rd-4th','5th-6th'):
            with self.subTest(band=band):
                raw=evidence_page();raw['exercise'].update(exercise())
                raw['html']=raw['html'].replace('stimulus_note_a','stimulus_source_a').replace(
                    'stimulus_note_b','caption_source_a_text')
                questions=raw['exercise']['questions']
                questions[0].update(prompt='Identify one fact from Source A and give its number or date.',
                    answer='The ceremony begins November 11, or the library recorded 36 visitors.')
                questions[1].update(prompt='Identify the opinion in Source A and explain why it is an opinion.',
                    answer='Most enjoyable is a personal judgment, not a measured fact.')
                before=deepcopy(raw)
                result=validate_design(raw,12,quality=workbook_config(band,simple=True),
                    expected_title='Fact and Evidence',require_coherent=True)
                rendered=fragment(result,preview=True);visible=plain_text(rendered)
                self.assertNotIn('<span',visible);self.assertNotIn('data-content=',visible)
                self.assertEqual(visible.count(SOURCE),1)
                self.assertEqual(result['exercise']['questions'][0]['answer'],before['exercise']['questions'][0]['answer'])
                self.assertEqual(raw,before)
