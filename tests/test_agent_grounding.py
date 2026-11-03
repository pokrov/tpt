"""Regress the Veterans Day answer-key mismatch, historical conflation and source layout."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from core.answer_grounding import answer_unit_bank, claim_issues
from core.review_format import ReviewFormatError
from core.history_checks import history_issues
from core.workbook_review import validate_review, review_varied_pack, review_schema
from core.task_visuals import answer_text
from core.student_workbook import source_markup

SOURCE = ('Citizens show great dedication by organizing food drives, cleaning public spaces, '
          'and preparing care packages all year round.')
WRONG = 'Community members display flags and listen to speeches.'
RIGHT = 'They organize food drives, clean public spaces, and prepare care packages.'


def page(answer=WRONG):
    return {'title':'Vocabulary in Context','page_number':1,
        'html':'<p>'+SOURCE+'</p><p>Based on Source A, what specific actions do citizens take?</p>',
        'exercise':{'render_mode':'authored','mechanic':'vocabulary', 'directions':'Read Source A.',
            'stimuli':[{'id':'a','label':'Source A','text':SOURCE}],
            'questions':[{'id':'2','prompt':'Based on Source A, what specific actions do citizens take?',
                          'answer':answer}]}, 'answers':'2. '+answer}


def verdict(answer=WRONG, supported=False, quote=SOURCE):
    return {'pages':[{'page_number':1,'source_accuracy':True,'no_answer_leak':True,
        'reason':'Review every printed detail.','issues':[],
        'question_checks':[{'id':'2','source_support':True,'skill_match':True,'answer_correct':True,
            'grade_match':True,'solution':RIGHT,'reason':'The passage lists three specific actions.',
            'answer_claims':[{'claim_id':unit['id'],'supported':supported,
                'evidence':[{'slot':'stimulus_a','quote':quote}] if supported else [],
                'reason':'Flags and speeches are absent.' if not supported else 'Supported by printed source.'}
                for unit in answer_unit_bank(answer)]}]}]}


class AnswerGroundingTests(unittest.TestCase):
    def test_false_claim_cannot_be_overruled_by_positive_summary_flags(self):
        self.assertIn('unsupported',str(validate_review(verdict(),[page()],require_claims=True)))

    def test_fabricated_or_wrong_source_quote_and_missing_evidence_are_failures(self):
        for quote in ('Citizens display flags and listen to speeches.', ''):
            raw=verdict(supported=True)
            check=raw['pages'][0]['question_checks'][0]
            check['answer_claims'][0]['evidence']=[] if not quote else [{'slot':'stimulus_a','quote':quote}]
            with self.assertRaises(ReviewFormatError):validate_review(raw,[page()],require_claims=True)
        raw=verdict(supported=True);raw['pages'][0]['question_checks'][0]['answer_claims'][0]['evidence'][0]['slot']='stimulus_b'
        second=page();second['exercise']['stimuli'].append({'id':'b','label':'Source B','text':SOURCE})
        with self.assertRaises(ReviewFormatError):validate_review(raw,[second],require_claims=True)

    def test_every_answer_unit_must_be_audited_and_valid_paraphrase_is_allowed(self):
        raw=verdict(answer=RIGHT,supported=True)
        self.assertEqual(validate_review(raw,[page(RIGHT)],require_claims=True),{1:[]})
        answer='They organize food drives. They also prepare care packages.'
        raw=verdict(answer=answer,supported=True)
        raw['pages'][0]['question_checks'][0]['answer_claims'].pop()
        with self.assertRaisesRegex(ValueError,'every numbered answer unit'):
            validate_review(raw,[page(answer)],require_claims=True)
        raw=verdict();raw['pages'][0]['question_checks'][0].pop('answer_claims')
        with self.assertRaisesRegex(ValueError,'answer_claims'):validate_review(raw,[page()],require_claims=True)

    def test_real_review_repairs_once_and_rechecks_both_bands_without_rewriting_source(self):
        for band in ('3rd-4th','5th-6th'):
            pack={'grade_band':band,'pages':[page()]}; repairs=[]
            def ask(prompt,validate,label,*args,**kwargs):
                pages=json.loads(prompt.split('Activities:\n',1)[1]);question=pages[0]['exercise']['questions'][0]
                if label=='Workbook independent solutions':
                    result=verdict();result['pages'][0]['question_checks'][0].pop('answer_claims')
                else:
                    self.assertIn('answer_claims',kwargs['response_schema']['properties']['pages']['items']['properties']['question_checks']['items']['required'])
                    result=verdict(answer=question['answer'],supported=question['answer']==RIGHT)
                return validate(result)
            def repair(number,previous,issues):
                repairs.append(issues);fixed=deepcopy(previous)
                fixed['exercise']['questions'][0]['answer']=RIGHT;fixed['answers']='2. '+RIGHT
                return fixed
            review_varied_pack(pack,ask,repair,require_claims=True)
            self.assertEqual(len(repairs),1)
            self.assertEqual(pack['pages'][0]['exercise']['stimuli'],page()['exercise']['stimuli'])
            self.assertEqual(pack['pages'][0]['exercise']['questions'][0]['answer'],RIGHT)

    def test_final_key_uses_canonical_answers_even_when_cached_key_is_stale(self):
        p=page(RIGHT);p['exercise_binding']={'status':'bound'};p['answers']='2. '+WRONG
        self.assertIn(RIGHT,answer_text(p));self.assertNotIn('speeches',answer_text(p))

    def test_genuine_personal_responses_remain_open_but_source_bound_ones_need_evidence(self):
        p=page('Accept a thoughtful personal suggestion with an explanation.')
        q=p['exercise']['questions'][0];q['prompt']='Suggest your own way to thank a volunteer. Explain your choice.'
        check={'answer_claims':[{'claim_id':1,'supported':True,'evidence':[],
                                 'reason':'A relevant personal suggestion is the requested criterion.'}]}
        self.assertEqual(claim_issues(check,q,p),[])
        q['prompt']='Based on Source A, suggest your own way to describe the listed actions.'
        self.assertTrue(claim_issues(check,q,p))


class HistoryAndLayoutTests(unittest.TestCase):
    def test_actual_varied_validation_requires_historical_content_repair_in_both_bands(self):
        from tests.test_student_workbook import evidence_page, workbook_config
        from core.creative_generator import validate_design
        for band in ('3rd-4th','5th-6th'):
            raw=evidence_page()
            raw['exercise']['stimuli'][0]['text']='Veterans Day is observed to honor all living military veterans.'
            with self.subTest(band=band),self.assertRaisesRegex(ValueError,'factual correction required'):
                validate_design(raw,12,quality=workbook_config(band,simple=True),
                                expected_title='History Evidence',require_coherent=True)

    def test_verified_history_errors_require_content_repairs(self):
        cases=[('November 11 marks the exact hour fighting officially stopped.', '', ''),
            ('Veterans Day is observed to honor all living military veterans.', '', ''),
            ('The armistice was signed at 11 a.m. on November 11, 1918.', '', ''),
            ('The armistice took effect in 1918.', 'What happened on the eleventh hour?', 'An armistice was signed.')]
        for source,prompt,answer in cases:
            p={'title':'Veterans Day','exercise':{'stimuli':[{'text':source}],
                'questions':[{'id':'1','prompt':prompt,'answer':answer}]}}
            self.assertTrue(history_issues(p),source+prompt)
        for source in ('Veterans Day honors all veterans, living and deceased, and especially thanks living veterans.',
                       'Veterans Day particularly honors living military veterans.',
                       'The armistice was signed earlier and took effect at 11 a.m.',
                       'Ceremonies especially thank living military veterans.'):
            self.assertEqual(history_issues({'title':'Veterans Day','exercise':{'stimuli':[{'text':source}]}}),[])

    def test_compacted_matching_sources_keep_block_boundaries_and_readable_separator(self):
        for band in ('3rd-4th','5th-6th'):
            from tests.test_student_workbook import workbook_config
            config=workbook_config(band,simple=True)
            first=source_markup({'id':'a','label':'Source A'},'The armistice took effect in 1918.',config,inline_label=True)
            second=source_markup({'id':'b','label':'Source B'},'The holiday name changed in 1954.',config,inline_label=True)
            self.assertIn('display:block',first)
            self.assertIn('</strong>: The armistice',first)
            self.assertIn('margin:0 0 2mm',first+second)
            external=source_markup({'id':'a','label':'Source A'},'First note.',config,inline_label=True,external_label=True)
            self.assertIn('display:block',external)
            # Real text layout: short sources must not collapse onto one line.
            from weasyprint import HTML
            from core.creative_layout import document_markup
            markup=''.join(source_markup({'id':s.lower(),'label':'Source '+s},'A short note.',config,inline_label=True) for s in 'ABCD')
            doc=HTML(string=document_markup([markup],config['student_font_pt'])).render()
            labels={box.text:box.position_y for box in doc.pages[0]._page_box.descendants()
                    if type(box).__name__=='TextBox' and box.text in {'Source '+s for s in 'ABCD'}}
            self.assertEqual(len(labels),4)
            self.assertEqual(len(set(labels.values())),4)
