# How Plants Grow V3.1 — offline final review package

Status: **technically ready for independent publication review; not approved for sale**. Created 2026-11-03. No Docker deployment, provider request or TPT action was made.

## Final files

- [Color PDF](../../tmp/workbook-v31-output/how-plants-grow-v3.1-letter-color.pdf) and [ink-friendly PDF](../../tmp/workbook-v31-output/how-plants-grow-v3.1-letter-ink.pdf): 18 US Letter pages each.
- [Color contact sheet](../../tmp/workbook-v31-output/color-contact.png) and [ink contact sheet](../../tmp/workbook-v31-output/ink-contact.png).
- Full-page PNGs: `tmp/workbook-v31-output/previews/{color,ink}/` (18 each).
- 1600-pixel previews of pages 3, 5, 7, 9, 11, 13, 15, 16, 17 and 18 in `tmp/workbook-v31-output/full-resolution/{color,ink}/`.
- [Scientific source review](HOW_PLANTS_GROW_V31_SCIENCE_REVIEW.md), [commercial-rights audit](HOW_PLANTS_GROW_V31_RIGHTS_AUDIT.md), [asset ledger](../../tmp/workbook-v31-output/asset-provenance.json).

## Page-by-page change log against V3

| Page | V3.1 change |
| --- | --- |
| 1 | Approved cover composition retained; V3.1 draft footer. Ink cover now has a true white background. |
| 2 | Teacher quick-start content and layout retained; edition footer updated. |
| 3 | Approved reading layout and artwork retained. Pointers compared with bean-seed sources; expert anatomy sign-off remains open. Edition footer updated. |
| 4 | Canonical student questions retained. |
| 5 | Light-energy, carbon-dioxide and water inputs now have directed arrows. Oxygen has an outward arrow. Sugars are called out at the leaf without suggesting they leave the plant. Energy is distinguished by a dashed arrow in both editions. |
| 6 | Canonical student questions retained. |
| 7 | Soil-water entry and upward transport are drawn on/beside the plant. Roots, leaves and xylem **inside** the stem have distinct labels. |
| 8 | Canonical student questions retained. |
| 9 | Five stage labels and shuffled order retained. Tighter flowering-plant and pod crops remove neighboring artwork fragments; grayscale derivatives match. |
| 10 | Observation protocol retained. |
| 11–12 | Sketch boxes enlarged from 43 to 60 points while retaining date, day, condition, root, shoot, leaves, height in cm and notes. |
| 13 | Claim and reasoning now have three handwriting lines each; all four prompts and the optional starter remain. |
| 14 | Same four synthesis questions; handwriting line spacing increased. |
| 15 | Reading 1 key prints question wording, correct letter and answer text, source evidence and acceptable responses. Germination evidence now includes the canonical water sentence. |
| 16–17 | Reading 2/3 keys use the same clearer hierarchy and canonical answers. |
| 18 | Inquiry guidance uses more readable text spacing; scoring and misconception guidance remain. |

The key remains four pages. Combining it further would force the source excerpts, model answers and acceptable alternatives into narrower or smaller text.

## Verification results

| Check | Result |
| --- | --- |
| V3.1 + V3 + V2.1 + V2 automated tests | **14 passed**. V3.1 checks all 12 question prompts and printed key answers in color and ink, canonical passages, diagram labels, observation fields, page count/dimensions and draft release gate. |
| Scheduler, existing formats and active grades | **36 passed** in the existing offline Docker test image with `--network none` and a read-only project mount. |
| PDF structure | 18/18 US Letter pages in each edition. Manifest PDF SHA-256 values match the files. Extracted educational text is identical across color and ink. |
| Rendering and visual inspection | 18/18 pages of each edition rendered to PNG. Both contact sheets reviewed; selected pages were also inspected at 1600-pixel height. No observed clipping, overlapping labels, broken arrows, blank pages or page-number mismatch. Physical printer proof remains open. |
| Preservation | Baseline hashes match for both original V3 PDFs, all **33** library PDFs and `local-data/state.json`. The prior V3 asset ledger hashes also match all 18 existing raster assets. Library still has **33** records. `local_schedule.enabled=false`. |
| Provider and publishing actions | No Gemini, Cloudflare or other generation call in this V3.1 work; no app rebuild/deployment, schedule change, library write or TPT upload. |

## Human review checklist and blockers

- Have an elementary science educator or botanist inspect the page 3 anatomy leaders, plant drawings, photosynthesis arrows, water pathway and five life-cycle images.
- Have a teacher check the difficulty of each question, all 12 keys and rubrics, the observation protocol and the amount of writing/sketch space on a printed US Letter copy.
- Confirm ownership and commercial-use evidence for each artwork, derivative, font, brand element, educational text and programmatic diagram. All ledger entries remain **Unverified**.
- Review a physical color and black-and-white print proof for contrast, legibility, margins and handwriting usability.
- Record separate human science, answer, layout and rights approvals before any commercial release. The PDFs continue to say **Draft**; no automatic readiness decision was made.

## Files and rollback

Changed or added: `design/build_v3_prototype.py` (optional V3.1 parameters; V3 defaults preserved), `design/build_v31_workbook.py`, `design/assets/v31-stage-{4,5}{,-ink}.png`, `scripts/build_v31_offline.py`, `tests/test_workbook_v31.py`, this report, the V3.1 science review, the rights audit and `PROJECT_HANDOFF.md`. Versioned outputs are only under excluded `tmp/workbook-v31-output/`.

The pre-edit source archive and hash lists are under excluded `tmp/workbook-v31-baseline/`. To roll back, stop using the V3.1 outputs and restore only the reviewed source files from `v3-source-before-v31.tar.gz`; do not replace `local-data/` or the existing V3 PDFs. Compare the baseline hash lists before and after any restore. No container was rebuilt or restarted.
