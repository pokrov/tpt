# Project context: Classroom Workbook Agent and Offline Listing Studio

Updated: 2026-10-31, Africa/Casablanca.

This is a technical handoff for a future developer or coding agent. It describes the current project, user requirements, implementation boundaries, operation, and validation history. It is documentation, not a new set of standing agent instructions. Current user instructions take precedence. Previously supplied AGENTS.md instructions were explicitly revoked by the user; their continued presence on disk does not reinstate them.

## 1. Product and user intent

The product is **OUR CLASSROOM COLLECTION**: printable classroom workbooks intended for sale on Teachers Pay Teachers (TPT). Although the repository is named kids-storybook-agent, the active product is a teacher workbook generator rather than a storybook generator.

The user wants to:

- Generate useful, original, grade-appropriate books with readable layouts, meaningful illustrations, written activities, and a complete final answer key.
- Support grades **3–4** and **5–6**.
- Create a separate downloadable preview containing **exactly three student pages**, with PREVIEW watermarks.
- Produce an editable product title and detailed TPT description from each book.
- Use the listing tool both inside the workbook application and as an independent local Python application.
- Process text-based, scanned, and mixed PDFs offline, without AI services or API keys for listing generation or OCR.
- Offer “Create preview & listing” on existing library books and after generation, avoiding repeated PDF uploads.
- Let the generator save structured JSON that the listing tool can read, so descriptions reflect final book content.
- Describe the activities students perform rather than copying raw source passages, table values, or card contents into marketing text.

The workbook generator itself uses external text/image services. The fully offline requirement applies to the preview/listing/OCR workflow, not to original workbook generation.

## 2. Locations and source identity

Actual application directory:

```text
C:/Users/Mehdi/Downloads/kids-storybook-agent-main/kids-storybook-agent-main
```

User-identified upstream: https://github.com/medshakespear/kids-storybook-agent

The application is an extracted source copy without Git metadata. An exact upstream commit or reliable uncommitted diff cannot be inferred from this installation. Preserve it before considering source migration or repository setup.

The chat's original working directory was `C:/Users/Mehdi/Documents/ChatGPT/Book Agent`. It has disappeared during previous work. Do not assume that path exists; set an explicit valid working directory for shell commands.

Recent source-only staging and QA files are under:

```text
C:/Users/Mehdi/.codex/visualizations/2026/10/27/01a17df4-e667-7202-b1c8-5b70ac35f4fb/listing-quality
```

That staging copy excludes credentials and persistent book/state data. Older PROJECT_HANDOFF.md backup paths may refer to deleted workspace folders; check existence before relying on them.

## 3. Applications and persistence

| Component | Main workbook application | Independent listing application |
| --- | --- | --- |
| Local URL | http://127.0.0.1:8080 | http://127.0.0.1:8081/listing-tool/ |
| Entry point | `local_server:app` | `listing_server.py` |
| Compose file | `compose.local.yaml` | `compose.listing.yaml` |
| Compose project | `classroom-workbook-local` | `classroom-listing-offline` |
| Service | `web` | `listing` |
| Container | `classroom-workbook-local-web-1` | `classroom-listing-offline-listing-1` |
| Image | `classroom-workbook-local-web` | `classroom-listing-offline-listing` |
| Server | Gunicorn, one worker/four threads | Flask standalone server |
| Provider credentials | Existing `.env.local` | Not supplied |
| Persistence | `./local-data:/data` | Listing job directory writable; output library read-only |

URLs/containers above describe the established deployment, not a guarantee that either process is running at the time this document is read. Main port can be overridden by LOCAL_PORT.

Main persistent paths:

```text
.env.local                             local settings and provider credentials
local-data/state.json                   history and saved local schedule/attempt markers
local-data/output/*.pdf                 completed books
local-data/output/*.product.json        optional PDF-bound product facts
local-data/listing-previews/<job-id>/    copied inputs, extracted facts, options, exports, edits
assets/store-logo.png                   product branding
```

`core/paths.py` uses DATA_DIR, then Railway volume configuration or project fallback. Local Docker uses `/data`. The standalone listing container mounts `local-data/output` at `/library:ro` and sets LISTING_LIBRARY_DIR=/library. It does not load workbook state or start a scheduler. LISTING_DATA_DIR can override standalone job storage.

There is no database. JSON state is atomically replaced. Background generation job tracking is in memory and does not resume after restart. Listing files persist independently of session cookies. No automatic listing-job retention cleanup is enabled.

## 4. Technology and dependency boundaries

- Python 3.11 Docker base.
- Flask 3.1.2; Gunicorn 23.0.0 for the workbook server.
- WeasyPrint 66.0 for printable workbook rendering.
- OpenAI Python SDK 1.109.1 is also used as transport for Gemini's compatible endpoint; installing it does not mean OpenAI service is the default.
- Pillow, requests, python-dateutil, tzdata, tinycss2.
- Listing: pypdf 6.x, ReportLab 4.x, pypdfium2, and local Tesseract with English data.
- `requirements-listing.txt` contains standalone Python dependencies without AI SDKs. Tesseract is an OS dependency installed by both Docker images.

Initial dependency/image installation needs internet. Once installed, listing extraction, OCR, preview assembly, and deterministic copy generation work offline. Workbook generation still needs its configured providers.

## 5. Workbook generation architecture

| File/module | Responsibility |
| --- | --- |
| `webhook_server.py` | Dashboard/library, generation APIs, background queue, PDF downloads, listing blueprint registration |
| `local_server.py` | Local entry, shared generation lock, daily/weekly schedule controls and scheduler |
| `cron_job.py` | Batch planning and generation; saves successes independently |
| `core/pipeline.py` | Shared end-to-end generation, artwork, staged PDF publication, ancillary product JSON |
| `core/reading_generator.py` | Reading/QCM authoring |
| `core/reading_answer_review.py`, `reading_bindings.py` | Reading answer review and binding |
| `core/varied_generator.py` | Grade-specific constraints for written varied packs |
| `core/creative_generator.py` | Varied content/design authoring and artwork orchestration |
| `core/creative_layout.py` | Sanitized printable layout, physical measurement, continuations, final key and PDF |
| `core/content_binding.py`, `activity_stimuli.py`, `label_bindings.py` | Keep displayed sources/tasks/labels attached to canonical content |
| `core/answer_grounding.py`, `answer_evidence.py`, `matching_grounding.py` | Canonical answer units, literal source evidence, matching review |
| `core/review_format.py` | Bounded repair of malformed audit responses |
| `core/calculation_attachment.py`, `math_result_recovery.py` and related modules | Numeric binding, validation and scoped recovery |
| `core/providers.py`, `credential_pool.py`, `runtime.py` | Providers, credentials, concurrency, deadlines and failure handling |
| `core/state_manager.py` | Atomic JSON state persistence |
| Calendar/reference modules and `calendar.json` | Event selection, date rules and reference context |

Pipeline outline:

1. Validate active grade, book type, provider configuration and runtime paths.
2. Generate the selected reading or varied canonical story data.
3. Perform the existing content, source, answer, arithmetic, grade and layout checks/repairs.
4. Count physical sheets and generate illustrations in a temporary directory.
5. Render a staged PDF; atomically publish it under a date/grade/title/UUID filename.
6. Remove transient artwork references from returned story data.
7. Save adjacent product facts from the final story and physical page mapping.
8. Return the completed story/PDF for library/history handling and the optional listing action.

Product JSON is ancillary: failure sets `product_info_status=unavailable`, keeps the successful PDF, and allows listing extraction/OCR fallback. It does not trigger another book generation.

## 6. Book types and quality contracts

Only `3rd-4th` and `5th-6th` are active. Older grade entries remain in configuration but do not enable those grades.

### Reading/QCM (`reading_qcm`)

- Default book type.
- Normally 12 pages: cover, five reading pages, five matching question pages, final answer key.
- Five questions per reading, four choices per question: normally 25 questions.
- Configured passage ranges: 220–280 words for grades 3–4; 320–380 for grades 5–6.
- Reviewed question data drives the printed choices and final key. Illustrations must not supply necessary answer evidence.

### Varied written activities (`varied_activities`)

- Sources and written tasks can include comprehension, vocabulary, evidence, sequencing, comparison, data, arithmetic, word problems and elapsed time.
- Grade-specific constraints include two items per activity and substantial writing space.
- Short-response panels are configured at 35mm, extended responses at 50mm, minimum answer width 150mm.
- Continuations are supported, bounded to one extra sheet per activity and a 16-page total cap. Never assume all varied books have 12 pages.
- No drawing/craft tasks in the supported written-workbook flow.

Shared print requirements: A4 portrait, store branding, readable student text, useful artwork, adequate response space, one complete final key, no student solution leaks, clipping, overlap or empty pages. Active student minimums are 12pt for grades 3–4 and 11pt for grades 5–6. Key layouts have their own smaller existing policy; assess key readability separately if reported.

## 7. Providers, schedules and queue behavior

Default source configuration uses Gemini for text/planning/design and Cloudflare for illustrations. `core/providers.py` currently names `gemini-3.5-flash-lite` as the default; GEMINI_TEXT_MODEL can override it. This is a code observation, not a claim about current service availability or the user's secret configuration.

Numbered credential slots 1–4 are supported with legacy aliases. Selection stays on a healthy credential and handles quota/auth/transient failures with bounded failover/cooldowns. Account/project quota grouping can mean several keys share an exhausted quota. Gemini text concurrency is constrained to one. OpenAI is explicit opt-in, with no automatic fallback. Groq is retired. Gemini image review is disabled; file validation and content/answer review remain separate active checks.

The main app has one generation executor worker and accepts at most two queued/running background jobs. On-demand and scheduled work share the generation lock. Do not add another workbook process/scheduler expecting the in-memory lock to coordinate across processes.

Saved web schedule settings in `state.json` take precedence over legacy environment settings. Local schedule validation supports daily/weekly operation, time, timezone, count, book type and rotating or explicit grade. `/local/schedule` handles GET/PUT; an active generation blocks schedule updates with 409. The default timezone is Africa/Casablanca. Windows must remain awake and Docker running.

Attempt markers prevent automatic same-day repeat spending after interruption; jobs are not replayed on restart. Calendar selection uses configured date windows and real event rules. Some religious-date tables cover only 2026–2027 and require maintenance for later years. README and early handoff sections contain older descriptions; inspect current source/config before changing behavior.

## 8. Offline preview/listing architecture

| File | Responsibility |
| --- | --- |
| `listing_tool/engine.py` | Page inspection, facts, selection validation, watermarked preview and complete draft |
| `listing_tool/ocr.py` | Sparse/scan-page rasterization and bounded local English OCR |
| `listing_tool/product_info.py` | Safe projection from final canonical story; PDF hash/structure validation |
| `listing_tool/listing_copy.py` | Deterministic task classification and varied-book marketing copy |
| `listing_tool/worker.py` | Isolated processing subprocess; metadata-first, extraction/OCR fallback |
| `listing_tool/web.py` | Upload/library/review/create/edit/download routes and protection |
| `listing_tool/templates/listing_tool.html` | Shared user interface |
| `listing_server.py` | Independent app factory and loopback server |
| `LISTING_TOOL.md` | User/developer operating documentation |

### Integrated and standalone flows

Every available library PDF has **Create preview & listing**. Completed on-demand generation offers **Next: Create preview, title & description**. These actions open a form; creation is a POST rather than a side effect of visiting a link.

The standalone app offers a saved-book library selector as well as upload. A selected PDF and optional adjacent JSON are copied into a fresh random job directory. The library originals remain unchanged.

If trusted facts establish title, grade and three student pages, the tool can create outputs directly after the create action. Ambiguous older books open the review form. Users can edit page selection, topic, grade, title and description. Save edits before downloading final text. Existing saved edits are not silently replaced when templates change.

### Product JSON contract

Filename: `<pdf-stem>.product.json`; schema version remains 1 with optional backward-compatible task fields.

Top-level facts include PDF filename/SHA-256, topic, grade, book type, total physical pages, page records, declared skill references and content-review status. Page records contain physical number, heading, role, extracted canonical source/task text, reading/MCQ/question counts, continuation flag, optional opening-sentence summary, `task_prompts` and `task_directions`.

The projection excludes solution fields, key explanations, evidence/solver payloads, credentials and provider settings. It is not a full story archive. Student source/task text may naturally contain numerical givens; excluding answer fields is not a claim that the projection contains no numbers or answer-like words.

Validation checks schema/types/bounds, exact PDF SHA-256, actual page count/coverage, cover/student/final-key structure and skill references to real questions. Metadata files are size-limited and symlinks rejected. New task prompt count must match the recorded question count. Older files without optional task fields remain supported.

Missing, stale or invalid metadata falls back to PDF extraction/OCR with a note. The tool does not regenerate the book or silently label fallback facts as canonical.

### OCR and input limits

- PDF size: up to 80MB; physical page range: 3–100.
- Encrypted PDFs unsupported.
- Native text-rich pages use extraction; sparse or scan-heavy pages use PDFium + Tesseract English.
- Handles image-only and hybrid PDFs, including selectable footer text over page scans.
- Render cap: 3300 pixels per side and 12 megapixels.
- OCR: 25 seconds per page, 240 seconds total; outer worker timeout: 300 seconds.
- Unreadable/blank scans, missing OCR engine/data and exhausted time budgets yield errors rather than invented text.
- OCR facts are marked for review. Handwriting, tilted/poor scans and other languages are not established capabilities.
- Native cover title/grade take precedence when usable, preventing an OCR logo reading from replacing a good title.

### Preview contract

Exactly three distinct student pages, by physical PDF page number, in selected order. Recognized cover/key/teacher pages are blocked. Uncertain page roles need explicit review; detection is heuristic and cannot guarantee semantic safety on arbitrary imports.

Original page layout/artwork is retained; watermarks/footer are added and annotations removed. No cover/key is added. The preview uses original pages, never an OCR reconstruction. Originals are preserved.

### Listing sections and copy rules

Outputs include TITLE, DESCRIPTION, WHAT’S INCLUDED, SKILLS PRACTICED, WAYS TO USE, WHY IT’S USEFUL and PRODUCT DETAILS, followed by the digital-download notice and store attribution.

The latest varied-book copy fix:

- Prefers canonical `task_prompts`/`task_directions`; legacy combined text and headings remain fallbacks.
- Maps tasks to comprehension, vocabulary, evidence, correction, sequence, comparison, data, arithmetic, word problems and elapsed time.
- Describes student actions, excluding raw source/table/card dumps.
- Distinguishes direct arithmetic from word problems; numerical comparisons on data pages do not automatically imply textual comparison/ELA.
- Combines reading/math categories into a clearer title, capped at 80 characters.
- Counts activities without duplicating continuation sheets; advertises total questions only when all counts are known.
- Flags unknown task types and uses conservative generic wording rather than inventing an activity.
- Keeps reading/QCM's passage-and-question structure behavior.

Example corrected title: **Veterans Day Reading & Math Activities | Grades 5–6**. The checked book has 10 activities and 18 questions; these are facts about that book, not universal varied-book defaults.

This is template-based drafting, not an AI semantic author or factual audit. It does not verify history, math-answer correctness, picture content, grade appropriateness or TPT search performance. Imported PDF headings/text and OCR errors can affect copy; review exports before publishing.

## 9. Routes and local access boundaries

Main routes include `/`, `/books`, `/api/books`, `/health`, `/output/<filename>`, `/generate`, `/generation-jobs`, job status/diagnostics, `/local/schedule`, `/local/worker-status`, and local daily-batch controls.

Listing blueprint prefix: `/listing-tool`.

```text
GET       /listing-tool/
GET       /listing-tool/library
GET/POST  /listing-tool/from-library/<filename>
POST      /listing-tool/upload
GET/POST  /listing-tool/<job>
POST      /listing-tool/<job>/save
GET       /listing-tool/<job>/download/<kind>
```

Listing forms use CSRF/session protection and local Host restrictions. Integrated access honors existing WEBHOOK_API_KEY via X-API-Key or HTTP Basic (any username, existing key as password). The standalone app receives no provider env-file. Original uploads are not served through output-download routes. Library paths reject traversal and symlinks. Processing is serialized per process and uses random job directories. Sessions reset on application restart.

## 10. Operation and maintenance

Run these from the actual application directory. Docker Desktop must be running.

```powershell
# Build/start workbook application
docker compose --env-file .env.local -f compose.local.yaml up -d --build

# Build/start independent listing application
docker compose -f compose.listing.yaml up -d --build

# Workbook logs
docker compose --env-file .env.local -f compose.local.yaml logs --tail 150 -f web

# Stop the selected app, retaining persistent data
docker compose --env-file .env.local -f compose.local.yaml stop
docker compose -f compose.listing.yaml stop
```

Launchers also exist: `Start Local.cmd`, `Stop Local.cmd`, `View Logs.cmd`, `Start Listing Tool.cmd`, `Stop Listing Tool.cmd`. Local scripts are under `scripts/local.ps1`. Compose raw env-file format requires a compatible Docker Compose version (documented setup uses 2.30+).

Plain Python standalone setup: create a virtual environment, install `requirements-listing.txt`, install Tesseract English on PATH, then `python listing_server.py`. Default bind is 127.0.0.1:8081. Docker sets an internal all-interface bind while restricting the host port to loopback.

Source is baked into Docker images, not bind-mounted. Editing source alone does not update a running container. Documentation-only updates do not need a rebuild/restart.

Before a main-app restart, check `/local/worker-status` with existing authentication and wait for `active_jobs=0` and `generation_busy=false`. Also avoid interrupting active listing workers. Build/test an image while the existing service continues running where possible, then perform a fresh idle check immediately before activation. Preserve PDFs, product JSON, state, listing edits and settings. Do not dump `.env.local`, full environments or credentials into logs/handoffs. Never start a provider generation merely to prove a documentation or offline listing change.

Compose clears remote library/delivery/GitHub token settings in the local workbook service. Do not assume legacy Railway/remote delivery features are active.

## 11. Recent correctness work worth preserving

PROJECT_HANDOFF.md records the detailed chronology. Important current mechanisms include:

- Canonical answer-unit IDs: reviewers reference Python-authored answer units rather than reconstructing answer text. Unknown/missing IDs fail; negative reports remain negative.
- Literal evidence-bank IDs: Python resolves exact canonical source excerpts. Fabricated citations and wrong-source evidence remain invalid; no fuzzy evidence repair.
- Audit/content separation: malformed review format/citations receive bounded targeted audit corrections instead of automatically rewriting a correct exercise.
- Matching: complete numbered/lettered printed givens can supplement required source evidence under a restricted policy; local blind/authored map disagreement must be reported.
- `Statement` is an allowed neutral organizational table heading; this does not authorize inventing factual table contents.
- Math repair coherence: safe local evaluation fixes numeric metadata from bounded existing expressions; only conservative requested-quantity prose repairs are local. Grade revision and coherent question/calculation/key updates remain checked. Numeric answer-only provider repairs receive an immutable question/source payload and Python's verified result.

Do not fix future provider failures by deleting source/answer/grade checks, increasing spending unboundedly, hiding substantive page content or loosening evidence validity. Reproduce the specific issue and inspect existing scoped recovery modules first.

## 12. Validation history and limits of evidence

The following are recorded results from prior implementation work, not tests rerun while writing this context file:

- Connected library release: 89 relevant tests passed in the release image with networking disabled and no source mount, including real PDF rendering in both grades with mocked provider content. Live no-upload library workflows and three-page preview downloads were checked.
- Latest listing-copy release: 75 targeted tests passed in the isolated release image, with no network or provider calls. Main and standalone live HTTP workflows produced the revised Veterans Day listing and three-page watermarked preview. A pre-restart snapshot of 159 persistent files matched after activation.
- Later/other workbook work recorded in PROJECT_HANDOFF.md includes matching/evidence and math coherence repairs. The latest math deployment recorded 87 release-image math/web/queue/schedule/SDK/PDF checks plus 25 listing/OCR/library checks passing. Its pre-restart preservation check covered 175 persistent files.
- Two bounded live Gemini text-repair integration checks were performed for math coherence; no Cloudflare calls or full provider-generated book were part of those checks. Most test fixtures use mocked providers and real local PDF rendering.
- Historical full-suite runs were not completely green. The math handoff records a missing exact-puzzle-spec recovery issue and an older response-panel expectation, plus an obsolete retry-count assertion subsequently corrected and verified in focused tests. Do not claim a clean full suite without a new run and investigation.

Useful focused offline command (requires the prepared image):

```powershell
docker run --rm --network none -e LOCAL_SCHEDULER_THREAD=0 -e DATA_DIR=/tmp/listing-quality-tests classroom-workbook-local-web python -m unittest tests.test_listing_copy tests.test_listing_tool tests.test_listing_library tests.test_listing_ocr tests.test_web_generation_ui tests.test_local_server tests.test_local_schedule tests.test_library -q
```

Choose tests appropriate to the change; inspect fixtures for isolation before broad execution. Rendering/layout changes require actual PDFs and visual inspection, ideally both supported grades. Provider acceptance, offline correctness, rendered layout and semantic classroom quality are distinct claims.

## 13. Known limits and possible follow-up work

- Listing quality is bounded by deterministic task profiles and the accuracy of source metadata/extraction. Human edits remain useful, especially for unknown activity types.
- Listing creation does not inspect or correct factual errors already present in a book. The Veterans Day source text was not rewritten by the copy fix.
- Three preview pages are selected by role heuristics and explicit review; arbitrary imported books may have mislabeled or unrecognized answer material.
- OCR is English and tuned to clear printed scans; it does not guarantee names/numbers or handwriting recognition.
- No automatic TPT publishing, external upload, SEO performance measurement or keyword-market research is implemented by the listing tool.
- Listing jobs retain copied input PDFs indefinitely unless deliberately cleaned up. There is no UI retention policy yet.
- Calendar tables, legacy README wording, unsupported old grade configuration and remaining full-suite issues need deliberate maintenance, not automatic broad cleanup.
- There is no verified upstream Git baseline, and deleted staging paths limit some historical reproduction evidence.

Potential future improvements should preserve offline operation: richer canonical activity labels/skill tags, explicit preview-page recommendations from final book structure, an optional listing-quality review checklist in the editor, safe retention controls, and more task-profile coverage driven by actual generated books.

## 14. Starting point for the next developer

1. Confirm the actual directory and current user request; do not treat this context as authorization for unrelated changes.
2. Read current source for the relevant subsystem, plus LISTING_TOOL.md, LOCAL_SETUP.md and the newest applicable PROJECT_HANDOFF.md entries.
3. Keep credentials and production data out of fixtures/staging. Use explicit valid working directories.
4. Reproduce the reported defect on isolated inputs. Distinguish source-content defects, reviewer-format defects, layout failures, OCR mistakes and marketing-copy issues.
5. Make a focused fix, run meaningful tests, and render/inspect when layout changes.
6. If deployment is requested or implied by an implementation task, check activity before activation and verify live behavior without spending provider quota unnecessarily.
7. Record what changed, what was tested, what remains uncertain and whether existing saved books/edits are affected.

This context-file task changed documentation only. It did not restart services, generate books, modify settings, process additional PDFs or rerun the historical test suites.
