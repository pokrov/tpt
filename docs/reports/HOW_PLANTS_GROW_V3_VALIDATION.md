# How Plants Grow V3 — offline implementation and validation

## Deliverables

The V3 candidate is a separate offline edition. No deployed app route, V1/V2/V2.1 PDF, library state, schedule, provider setting or credential was changed.

- [Color PDF](../../tmp/workbook-v3-output/how-plants-grow-v3-letter-color.pdf) — 18 US Letter pages.
- [Ink-friendly PDF](../../tmp/workbook-v3-output/how-plants-grow-v3-letter-ink.pdf) — 18 US Letter pages.
- [Color contact sheet](../../tmp/workbook-v3-output/color-contact.png) and [ink contact sheet](../../tmp/workbook-v3-output/ink-contact.png).
- Individual full-page PNGs: `tmp/workbook-v3-output/previews/color/` and `tmp/workbook-v3-output/previews/ink/` (18 each).
- [Asset provenance manifest](../../tmp/workbook-v3-output/asset-provenance.json).
- [Scientific source check](HOW_PLANTS_GROW_V3_SCIENCE_REVIEW.md).

## Implementation

- Reused the approved V3 cover and first reading design with a draft footer; the prototype's default output remains unchanged. Added a white, grayscale low-ink cover variant.
- Built the remaining 16 pages in `design/build_v3_workbook.py` using the validated V2.1 canonical passages, questions and answer keys. Page 9 now uses original botanical stage art in shuffled order. Pages 5 and 7 use a whole-plant illustration with explicit educational labels.
- Produced artwork with Codex's built-in image-generation tool and made local crop/grayscale derivatives. No project Gemini or Cloudflare credentials or API calls were used. All asset rights are **Unverified**; the generated images require human scientific and commercial review.
- Kept the output in excluded `tmp/workbook-v3-output/`; the rollback snapshot is in excluded `tmp/workbook-v3-baseline/`.

## Verification

| Check | Result |
| --- | --- |
| V3, V2.1 and V2 focused tests | 12 passed. Covers canonical passages/questions, key inventory, 18-page count, US Letter, assets and review gates. |
| Scheduler, original formats and active grades | 36 passed in the existing offline Docker test image, with `--network none` and a read-only source mount. |
| Final PDF render | 18/18 color pages and 18/18 ink pages rendered to PNG; no rendering failure. |
| Visual QA | Reviewed both 18-page contact sheets and inspected enlarged reading/diagram and life-cycle pages. No observed clipping or overlap after correcting page 5 labels. Student writing areas and teacher-key page breaks are present. |
| Persistent library | 33 saved records; hashes of all 33 library PDFs match baseline. Both V2.1 PDFs and `local-data/state.json` match baseline hashes. |
| Schedule | `local_schedule.enabled=false` after final build. |
| Provider use | No live Gemini or Cloudflare generation or review. No deployment or TPT upload. |

## Visual checklist and limitations

- Cover and page 3 follow the approved prototype. Ink cover is white and uses grayscale art and an outlined badge. Page 9's ink art is grayscale.
- Pages 4, 6 and 8 have answer space for written work. Pages 11–12 have observation records and sketch areas. Pages 15–18 keep the teacher key separate from student pages.
- The design is an offline candidate. Reading pages 5 and 7 and key pages have generous white space; a teacher should judge whether their density and the 8-point diagram callouts suit the intended print use. A high-resolution print proof has not been completed.
- Scientific correctness of illustrations and labels, answer-key accuracy, lesson usability, all commercial-use rights and final layout approval require separate human checks. No workbook has been marked ready to sell.
- The project checkout has no `.git`; rollback is the source and PDF hash snapshot in `tmp/workbook-v3-baseline/`. This snapshot intentionally excludes secrets and persistent private content. Restore the saved source archive only after reviewing paths, and verify original library hashes before and after any restore.

## Files added or changed

- `design/build_v3_prototype.py` (optional draft/ink cover behavior; prototype defaults retained)
- `design/build_v3_workbook.py`
- `design/assets/bean-growth-cover-art-ink.png`
- `design/assets/v3-bean-plant*.png`, `design/assets/v3-life-cycle-sheet*.png`, `design/assets/v3-stage-*.png`
- `scripts/build_v3_offline.py`
- `tests/test_workbook_v3.py`
- `docs/reports/HOW_PLANTS_GROW_V3_SCIENCE_REVIEW.md`
- `docs/reports/HOW_PLANTS_GROW_V3_VALIDATION.md`
- `PROJECT_HANDOFF.md`

## Rebuild / rollback

From the project root, run `python -m scripts.build_v3_offline` with ReportLab, Pillow and pypdf installed. It writes only the separate V3 output directory.

For rollback, stop using the V3 drafts, inspect `tmp/workbook-v3-baseline/approved-v3-and-v21-source.tar.gz`, and restore only its V3/prototype source files as needed. Keep `local-data/` and the existing PDFs untouched. The baseline hash lists can verify preservation. No Docker image was rebuilt or restarted.
