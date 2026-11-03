"""Written-workbook prompts without legacy craft/picture-puzzle instructions."""
import json

from core.simple_exercises import exercise_guidance


def written_quality_guidance(grade_band):
    from core.history_checks import history_guidance
    return (f'Written workbook quality for {grade_band}: use complete short printed sources, '
            'clear questions and full-width white response areas. Each page teaches a useful '
            'skill through a different student action. Illustrations clarify the context but '
            'never supply exact quantities or answers. Use age-appropriate art, readable '
            'labels, coordinated colors and generous writing space. Do not repeat a question '
            'in different words. Keep every needed source, data value and answer criterion. '
            'Positional words must match the final layout. No teacher guide. '
            'All source, caption, passage, direction and question text fields contain plain text only. '
            'Never place HTML, escaped HTML or data-content placeholders inside those text fields; '
            'content-slot markup belongs only in the separate html layout. '
            + exercise_guidance(grade_band)+' '+history_guidance())


def written_plan_prompt(theme, grade_band, config, source_context, count, book_title=None):
    return (f'Plan an ORIGINAL illustrated reading, writing and mathematics workbook for {grade_band}. '
            f'Theme: {theme}. Teacher brief/inspiration: {source_context or theme}. '
            f'Plan exactly {count} distinct student activities. All use render_mode="authored". '
            'Supply at least five genuinely different actions, with no action on more than three pages. '
            'Include source-supported reading and useful grade-appropriate mathematics; weave word '
            'problems into the topic instead of attaching unrelated calculations to vocabulary tasks. '
            'Use short complete sources and one or two focused questions per page. Each quantitative '
            'question asks for one outcome with explicit units and all needed data. '
            f'Art direction: {config["illustration_style"]}. '
            'Return JSON: title <=80 characters, overview <=350, art_direction <=650, '
            'character_description <=350, cover_brief <=800 and pages. Every page needs title <=80, '
            'learning_goal <=650, activity_concept <=650, layout_brief <=650, render_mode="authored" '
            'and a short mechanic describing the actual student action. Omit mechanic_constraints. '
            'Vary compositions while preserving readable sources and writing space. The cover has '
            'only a short title, grade label and large image on a colorful shaped background. '
            'Do not imitate a seller or invent factual claims; label invented scenarios fictional. '
            + written_quality_guidance(grade_band)
            + (' Exact requested title, use verbatim: '+json.dumps(book_title) if book_title is not None else ''))
