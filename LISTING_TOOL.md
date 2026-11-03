# Offline PDF Listing Studio

Two local entry points share one Python implementation:

- In the existing workbook app, choose **PDF preview, title & description** at http://127.0.0.1:8080/ or open http://127.0.0.1:8080/listing-tool/.
- Double-click **Start Listing Tool.cmd** for the independent app at http://127.0.0.1:8081/listing-tool/. **Stop Listing Tool.cmd** stops only that app. Docker Desktop must be running. Initial image/dependency installation needs internet; PDF processing makes no AI/API requests and works offline after installation.

Alternatively, with Python 3.11+ installed, create a virtual environment, install `requirements-listing.txt`, install Tesseract with English language data and add its executable to PATH, then run `python listing_server.py`. Docker installs this OCR engine automatically. This starts only the listing tool, without importing workbook providers or starting its scheduler. It binds to 127.0.0.1:8081. No provider credentials are required.

## Workflow

Varied-book listings describe student actions instead of reproducing source passages, card contents or table cells. Local templates identify tasks such as vocabulary, fact/opinion with evidence, corrections, sequencing, comparisons, data interpretation, arithmetic, word problems and time calculations. Titles reflect the reading/math mix and are capped at 80 characters. Activity and question counts come from known structured page facts; uncertain counts are omitted. Unknown task types remain generic and are flagged for manual review. Reading/QCM listings retain their passage/count format.

New product-information files keep `task_prompts` and `task_directions` separately from source text. The listing classifier prefers these fields; older JSON files and imported PDFs still work through heading/text inference. This changes listing copy only: it does not rewrite PDF content or alter answers, generation prompts, schedules or provider usage. Saved listing edits are not automatically overwritten; create a new listing or regenerate its draft to use the improved templates.

### Saved books: no upload required

Each available book in the existing workbook library has **Create preview & listing** beside its PDF download. A completed on-demand generation also offers **Next: Create preview, title & description**. Open that option and choose **Create preview, title & description** to generate all three outputs. Uncertain legacy title/grade/page selections open the review form instead of inventing facts.

The independent app has **Choose a saved book from the library**. Its Docker service mounts only `local-data/output` read-only at `/library`, including adjacent product-information JSON files, without loading workbook state or provider settings. Plain Python defaults to `local-data/output`; `LISTING_LIBRARY_DIR` can select another local PDF library.

Newly generated PDFs have an adjacent `<pdf-stem>.product.json` file containing final passage/activity titles, physical cover/student/key page structure, canonical question counts, literal source opening sentences, and declared reading-skill references. No solutions, key explanations, review evidence, credentials or solver payloads are stored in this projection. The file includes the PDF SHA-256 hash; the tool checks it, page coverage and question references before using the facts without OCR. Older books, missing JSON and mismatched/invalid JSON use PDF extraction and local OCR. Existing PDFs are not regenerated and older books are not falsely labeled as canonical metadata. Copies and listing results live in separate random upload directories; original library PDF/JSON files remain unchanged.

Product-information saving happens after a successful PDF save. Failure to write this ancillary file leaves the completed book available and allows extraction/OCR fallback. This feature does not add provider calls or change generation prompts, reviews, layouts, schedules or state writes.

### Uploaded books

1. Upload a text, scanned, or mixed PDF (at most 80 MB, 3–100 pages). Local English OCR runs automatically for pages with little usable text or a large scan image and limited selectable text. Encrypted PDFs remain unsupported. Clear, upright printed text gives the best results; handwriting or unreadable scans may not be recognized.
2. Review the extracted topic, grade band and page inventory. Only grades 3–4 and 5–6 are offered. Cover titles are estimated from the largest text; edit if necessary.
3. Choose **exactly three distinct student pages** by physical PDF page number, such as `2,3,4`. Detected covers, answer-key headings and teacher pages are blocked. Pages without recognized student markers must be reviewed and selected explicitly. Selection is heuristic, not semantic review; check the preview before sharing.
4. Create and download the three-page **PREVIEW** watermarked PDF. No cover or key is added. Original pages/artwork are preserved; annotations are removed from the sample. The original workbook is unchanged.
5. Review/edit the title and complete listing, then **Save my edits** before downloading the UTF-8 text files. All requested sections are included: TITLE, DESCRIPTION, WHAT’S INCLUDED, SKILLS PRACTICED, WAYS TO USE, WHY IT’S USEFUL, PRODUCT DETAILS.

The draft uses deterministic templates and extracted headings, optional literal opening sentences, recognized reading/question structures and keyword-based skills. It does not write AI prose, infer topic facts, verify answer correctness, describe pictures, invent vocabulary lists or assert an editable/static format. Five-per-reading wording requires the corresponding page structure. Ambiguous details remain generic or need editing. OCR pages are labeled in the inventory and review notes; check recognized names, numbers, grades, titles and page roles against the original. The preview uses the original pages, not an OCR reconstruction. This is an editable listing draft, not automatic publication approval.

## Storage and boundaries

The integrated app uses `DATA_DIR/listing-previews/<random-id>/`; the separate Docker app mounts `local-data/listing-previews/` at the same host location. Plain Python defaults to `local-data/listing-previews/`, with an optional `LISTING_DATA_DIR` override. Each upload gets its own original PDF, extracted facts, options and results. Upload originals are never exposed by a download route. They remain on disk for reviewing/rebuilding; no automatic retention cleanup is enabled. Remove only an unwanted upload's own random-ID folder while the listing tool is idle.

Nothing reads or writes workbook `state.json`, schedules, existing library PDFs or provider settings. The standalone container does not receive `.env.local`. If `WEBHOOK_API_KEY` is configured in the existing app, the integrated tool requests HTTP Basic authentication: use any username and the existing access key as password. This is local app authentication, not an AI API key. Forms use CSRF protection. Sessions reset on application restart. Processing is serialized inside each process. A Python subprocess has a five-minute outer timeout; OCR has a four-minute total budget and a 25-second per-page timeout. Rendering is capped at 3300 pixels per side and 12 megapixels. Larger/complex scanned books may need splitting. The two app processes use distinct random upload directories.

Rebuilding the existing baked-source image is required to expose its new link. Check `/local/worker-status` first and wait for zero active jobs and `generation_busy=false`. Preserve loopback-only Compose ports, one existing workbook worker and all persistent data. Do not run a second workbook scheduler for the standalone tool.

## Verification

`python -m unittest tests.test_listing_tool -v` exercises real synthetic PDFs in both grades, varied exercises, exact page selection, watermarks, original preservation, no key/cover leakage, encrypted/textless inputs, the real worker subprocess, upload/edit/download, escaping, CSRF, host restrictions and existing-key authentication. Tests need only the standalone dependencies. Live providers are neither required nor called.

`python -m unittest tests.test_listing_ocr -v` additionally rasterizes real PDF pages to make image-only and hybrid fixtures, invokes actual offline Tesseract, verifies both grade bands, blocks detected key pages, preserves original images in previews, exercises the worker/upload/export flow and checks missing-engine/time-limit errors. These tests require local Tesseract; they run with networking disabled in the Docker image.

`python -m unittest tests.test_listing_library -v` checks canonical metadata in both grades, PDF hash/coverage/skill binding, continuation numbering, answer-payload exclusion, successful and failed pipeline metadata writes, no-upload library imports, stale-metadata fallback, source preservation, CSRF/path boundaries and the library/post-generation UI links.
