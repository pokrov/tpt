# How Plants Grow V2.1 — offline validation

Date: 2026-11-03 (Africa/Casablanca). Status: **Draft; publication blocked**. This is a separate fixed-editorial candidate. The deployed V2 app, original V2 draft, existing library, scheduler and provider settings were not changed. No Gemini or Cloudflare requests were made.

## Deliverables

- Color PDF: `tmp/workbook-v21-output/how-plants-grow-v2.1-letter-color.pdf` — SHA-256 `c9f6739e8a60c2b7ee4510fb0197bcb935f3c2e6dc037d78ae7ed09b073ce9f9`.
- Ink-friendly PDF: `tmp/workbook-v21-output/how-plants-grow-v2.1-letter-ink.pdf` — SHA-256 `61a32efc1fb5330b40bfd00677022139723b766852a7bcc8bd221ed4cdb94fce`.
- `tmp/workbook-v21-output/manifest.json` records profile `plant_reading_observation_v2_1`, PDF/content hashes, assets and separate review gates. All rights are Unverified; science is Unverified, answers/layout require validation.
- Rendered pages and complete contact sheets are in the same folder.

## Changes from V2

The V2.1 source and renderer are separate (`core/workbook_v21.py`, `core/workbook_v21_pdf.py`). The new cover uses a larger title and a locally drawn bean sequence. Reading pages have larger vector panels; seed vocabulary adds embryo, leaf text clarifies that plants use sugars for energy and growth. Each reading now has two MCQs, one sequence/classification task and one evidence-based written response. The key is generated from those same canonical questions. The teacher page adds a flexible sequence and unsuccessful-germination guidance. The protocol is numbered; the data page separates claim, two observations and reasoning.

The key needs four pages at readable type, so the new PDF has **18 pages**: student pages remain 3–14, with keys on 15–18. The cover no longer says “two-page key.” The V2 renderer and its 16-page files remain unchanged.

## Tests and inspection

- Current-source offline `tests.test_workbook_v21` and `tests.test_workbook_v2`: **10 passed**. These cover distinct question types, canonical answers, source-change invalidation, sequence-key shape, draft/rights defaults, 18-page rendering, key inventory and student-page answer leakage.
- Unchanged legacy `tests.test_book_types` and `tests.test_reading_answer_review`: **25 passed** in an isolated, no-network Docker test image with temporary state. A local attempt to run these legacy tests lacked the `openai` dependency; the isolated image supplied the project's normal dependencies and passed.
- Both PDFs have 18 pages at **612 × 792 pt**, no empty pages, key text only on pages 15–18, all expected page numbers, and no `Accept:` rubric marker on student pages. Every page of both PDFs was rasterized and visually inspected in complete contact sheets; the final adjusted covers were also inspected at higher resolution. No visible clipping, overlaps, broken labels, or missing answer areas were found at those review sizes. A physical classroom print proof has not been performed.
- All **486** persistent baseline files other than `state.json` still match their prior hashes. The V2 draft PDF hash is unchanged (`ba983cc8650282aa4704c870eac21e81c3a375be8fb4abaf4f6252ecf108411b`). State still holds **33** book records and 33 PDFs; the schedule is `enabled=false` and the last daily attempt remains 2026-11-02. V2.1 artifacts are outside `local-data`, so no library entry was added.

## Human publication checks

1. A science editor should verify each passage, diagram, question, classification and key against authoritative botany/elementary-science references, recording exact sources. The locally drawn seed/leaf/root diagrams are simplified educational models, not a verified botanical plate.
2. A grade 3–4 teacher should complete all student pages using the printed readings and a real or honestly unsuccessful observation log, then compare every answer and rubric against pages 15–18.
3. Print both editions at 100% on US Letter paper; check type size, ink use, writing/sketch space and diagram legibility at normal viewing distance.
4. Document ownership and commercial-use permission for the supplied logo, actual embedded font, locally authored diagrams and editorial text. Keep each asset Unverified until evidence is recorded.
5. Only after these independent checks should a human decide whether the candidate is suitable for a TPT listing. No automated approval, upload or publication has occurred. The suggested $3.99 price has not been validated.

## Reproduction and rollback

Run `python -m scripts.build_v21_offline` from the project root in an environment with the existing PDF dependencies. It writes only to excluded `tmp/workbook-v21-output/`; it does not read `.env.local` or call providers. To discard V2.1, remove its two new core modules, one build script, one test file and this report, and delete only `tmp/workbook-v21-output/` if the artifacts are no longer wanted. Do not alter `local-data/`, V2 source, Docker volumes or the saved schedule.
