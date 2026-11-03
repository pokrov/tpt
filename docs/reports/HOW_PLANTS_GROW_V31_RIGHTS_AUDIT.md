# How Plants Grow V3.1 — commercial rights audit

Status: **Unverified; commercial release blocked.** The [machine-readable asset ledger](../../tmp/workbook-v31-output/asset-provenance.json) lists every included raster file with path, SHA-256, origin, creator/provider, creation method, terms evidence and status. No blank license field is interpreted as permission.

| Asset group | Provenance | Missing evidence |
| --- | --- | --- |
| Botanical cover and page 3 art | Created for the V3 prototype with Codex built-in imagegen; see `design/ASSET_PROVENANCE.md`. | Exact generation terms/model record and commercial-use evidence; human science review. |
| Whole bean plant and life-cycle sheet | Created for V3 with Codex built-in image generation. | Exact generation terms/model record and commercial-use evidence; human science review. |
| V3/V3.1 grayscale and stage crops | Local Pillow derivatives of the above art; V3.1 stage 4/5 crops remove neighboring-art fragments. | Parent artwork rights, derivative record and human visual review. |
| Helvetica, Helvetica-Bold, Times-Bold, Symbol | These are the actual PDF font resource names in the local export. ReportLab references them as PDF base fonts; no font file was copied into this draft. | Confirm intended distribution and any font substitution/embedding rules with the final production environment. |
| Educational text and question/answer content | Canonical V2.1 offline editorial draft in `core/workbook_v21.py`; V3.1 reuses it without provider calls. | Document authorship/AI terms and run independent science, answer and copy review. |
| Vector arrows, labels and layouts | Programmatic PDF drawing in `design/build_v31_workbook.py`, adapted from V3. | Human approval of diagram accuracy and final publication layout. |
| Brand text | “Our Classroom Collection” supplied by the user; no store-logo bitmap is embedded in these PDFs. | Confirm brand/trademark ownership for marketplace use. |

Every record in the ledger remains **Unverified**. No TPT upload, sale approval or external publication was performed.
