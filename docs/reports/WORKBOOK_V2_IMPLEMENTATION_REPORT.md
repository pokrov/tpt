# Workbook V2 implementation and offline verification

Date: 2026-11-03 (Africa/Casablanca). Scope: a separate, grades 3–4 **plant reading and observation** draft profile. This source checkout is an extracted copy without Git metadata. The running Docker service was **not rebuilt or deployed** for this work. No Gemini or Cloudflare requests were made.

## Operational safeguards and rollback

- Before editing application source, `GET /local/worker-status` showed `active_jobs=0` and `generation_busy=false`. The existing 11:00 Africa/Casablanca daily schedule for eight `reading_qcm` books was saved through `PUT /local/schedule` with `enabled=false`. Final `GET /local/schedule` still shows `enabled=false`, `next_run=null`, count 8, time 11:00 and the prior `last_run` attempt on 2026-11-02 with exit code 1. The last-attempt metadata was preserved.
- The source-only pre-V2 baseline is `tmp/workbook-v2-baseline/source-before-v2.tar.gz`. It excludes `.env.local`, `local-data/`, generated PDFs, caches and `tmp/`. A separate complete `local-data/` copy and SHA-256 manifest are at `tmp/workbook-v2-baseline/local-data/` and `tmp/workbook-v2-baseline/data-sha256.txt`. The copy is 1.5 GB. These private backups are excluded from Docker builds and must not be committed or shared.
- All 487 files in the persistent-data hash manifest still match. State contains 32 generated-book records and `local-data/output/` has 32 PDFs. The original *How Plants Grow* PDF is unchanged: SHA-256 `d681b4ffda01c56b1519bd26eae2426da244b7b7d0b0f8194cca82d1e3b7a9e6`.
- To roll back **source only**, stop the local service, make a fresh copy of current files, and extract `source-before-v2.tar.gz` into this checkout. Then remove only the V2-only files listed below if desired. Do not restore the old state over newer user work; the backup `local-data/` is for selective recovery after comparing hashes. Restarting the existing container is a separate deployment decision.

## Implementation

- `core/workbook_v2.py` defines a versioned canonical plant draft with three 120–180-word readings, three questions per reading, literal evidence, answer/rubric fields, source hashes and known false-science guards. Editing a source invalidates dependent question hashes. The established `reading_qcm` and `varied_activities` formats were not changed.
- `core/workbook_v2_review.py` adds injectable, mock-tested science-claim and blind-answer reviewers. The blind review does not expose the proposed answer key; all question IDs and literal source evidence are required. Reviewer results never grant human approval. These reviewers have **no live provider adapter or automatic trigger yet**.
- `core/workbook_v2_pdf.py` renders a 16-page US Letter color or low-ink PDF (A4 is available to the renderer). It includes a teacher quick start, three passage/question pairs, deterministic labeled diagrams, bean life-cycle sequence, observation protocol and sketch logs, data writing, synthesis and a two-page key. No AI image decides a scientific answer. Student pages are separated from key pages. A draft warning remains on the PDF.
- `core/workbook_v2_store.py` stores hash-bound canonical and review sidecars under `local-data/v2-drafts/`, plus a versioned asset inventory with source hashes for the logo, diagrams, selected font and passages. It creates one immutable review unit for each original passage paragraph; all six units require source-linked human verification. Image, font, logo and text rights start `Unverified`. Science, answer, layout and commercial-rights checks are separate; weighted quality scores cannot override blockers. A human approval record also requires evidence for every asset, human verification of every gate and reviewer notes.
- `core/workbook_v2_web.py` adds a local-only V2 selection and quality dashboard. The `Create V2 draft` action renders two deterministic offline PDFs and registers the color draft in the existing library. It shares the generation lock and optional access key. The ink edition has a separate download. The UI is available **after a separately authorized Docker rebuild** at `/v2/plants/`; current runtime remains the previous image.

## Changed files

Application: `local_server.py`, `templates/books.html`, `core/workbook_v2.py`, `core/workbook_v2_pdf.py`, `core/workbook_v2_review.py`, `core/workbook_v2_store.py`, `core/workbook_v2_web.py`, `templates/workbook_v2.html`, `templates/workbook_v2_detail.html`.

Tests: `tests/test_workbook_v2.py`, `tests/test_workbook_v2_web.py`.

Documentation: `AGENTS.md`, `PROJECT_HANDOFF.md`, `docs/reports/WORKBOOK_V2_IMPLEMENTATION_REPORT.md`, `docs/reports/HOW_PLANTS_GROW_V2_VALIDATION.md`.

## Offline checks

- Isolated Docker image, no network or credentials, scheduler thread disabled: **78 tests passed** covering V2, reading generation, blind answer review, saved schedule, daily batch, listing library and book types. A second focused legacy/layout run: **41 tests passed** covering answer key, student workbook, both-grade layout, local server, varied format and print styles. After adding the final approval-transition and optional access-key regressions, all **8 V2 tests passed** on the refreshed image.
- Generated color and ink files in `tmp/workbook-v2-test-output/`. Both are 16 pages, 612 × 792 pt, with no empty pages; pages 15–16 are keys. A text check found no `Correct answer` or `Accept:` key language on pages 3–14. Every page of both editions was rasterized and visually inspected in contact sheets. No clipping or overlap was seen at this scale. See the validation report for the remaining human checks.
- The old 32 PDFs and state were not used as writable fixtures. The running service is healthy and idle; the saved schedule remains disabled.

## Live provider test budget and limits

Current offline V2 draft: **0 Gemini calls, 0 Cloudflare calls, 0 provider tokens**. The optional reviewers are not wired to live providers, so a live V2 generation test cannot yet be executed from this UI. A future bounded review-only test of one existing V2 draft would require **one science completion and one independent answer completion**, with a proposed hard cap of **2 Gemini calls total, no retries, 0 Cloudflare calls**. This is an additional validation budget, not an estimate for a fully AI-authored book. The review functions request up to 2,200 and 2,600 output tokens respectively; input tokens and actual usage are not measured by this offline implementation. No current configured model rate or provider pricing was verified, so a dollar cost is **unavailable**. Before any live test, wire a usage-recording adapter, verify the model and rates, set the call cap and request explicit approval. Existing reading generation has more planning, authoring, review, blind-solve and illustration calls, plus bounded repairs; do not use its schedule or generation route as a V2 test.

## Open issues

- Science claims have not been checked against authoritative external sources by a human. The offline false-claim guard and mocked reviewer do not establish scientific accuracy.
- Logo, local font, diagrams and text rights remain `Unverified`; the source PDFs do not establish commercial-use permission. No draft is approved for sale or TPT publication.
- The V2 draft has fixed editorial content. It is selectable and creates local PDFs, but it does not yet author new V2 topics with Gemini or create Cloudflare artwork. The live reviewer adapter, token accounting and hard transport cap are future work before a quota-consuming test.
- Visual inspection at contact-sheet scale is an offline layout check, not a classroom print proof or editorial review. Human review should inspect full-size printed pages, answer wording and each scientific claim.
