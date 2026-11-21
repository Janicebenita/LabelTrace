# Resettable demonstration script

Stop the running app. From `labeltrace`, run `.venv\Scripts\python.exe manage.py reset`, then `.venv\Scripts\python.exe manage.py start`. Open http://127.0.0.1:5173. Choose **Processor** (author), **Checker** (quality reviewer) or **Releaser** (release manager); the sign-in screen displays that role's local demo password. Use **Switch role** in the sidebar to change accounts.

1. **Processor (author):** inspect Overview and Products & facts. Four baseline PDFs are backed by approved synthetic specification v1 facts. Adult and pediatric variants have different addresses and identifiers; each has a box and carton.
2. **Author / Sources:** upload `fixtures/SYNTHETIC-adult-spec-v2.pdf` for adult. Inspect extracted text and manufacturer-address candidate, page and exact character span. The new address is 200 Research Way. Upload alone does not alter authoritative facts.
3. **Checker (reviewer):** switch role. In Sources, approve only the changed manufacturer-address candidate. Conflicting values would block this action.
4. **Author:** select Propose change for that candidate, inspect old/new values and reason, and submit for change review.
5. **Reviewer:** approve the source-backed change. Inspect impact: adult box/carton affected through their manufacturer-address dependency; pediatric box/carton explicitly excluded because their facts differ. Baseline pediatric artwork remains unchanged.
6. **Author:** in Impact explorer generate the adult box draft. In Label comparison inspect real before/after artwork and select the address field to inspect fact v2 and original source v2. Optionally also generate the affected carton; attempting generation for an unaffected label through the API is rejected.
7. **Author:** select the barcode defect fixture under Create a new immutable revision. Validate. The rendered QR decodes to `DEMO-WRONG-CODE` while the approved pack ID is `SYN-A150-B100`; database strings for the ordinary rendered identifier remain equal. This proves the checker reads actual artwork pixels.
8. **Releaser:** in Releases attempt Check & release. The API rejects absent successful validation/approval and saves a blocked-release audit event.
9. **Processor:** regenerate from current facts; this creates a new immutable clean revision. Validate it. **Checker:** approve the exact revision. The approval records hash, validation, dependency snapshot and reviewer. Optionally approve the unchanged pediatric box baseline to observe that its approval stays valid.
10. **Author:** without editing any label, upload `fixtures/SYNTHETIC-adult-spec-v3.pdf` (300 Research Way). Repeat reviewer evidence approval, author change proposal and reviewer fact-change approval.
11. **Releaser:** attempt release of the previously approved adult revision. It is Stale and explicitly blocked because `adult.manufacturer_address` has a newer approved version. Its original approval remains visible; the pediatric approval remains current.
12. **Processor:** regenerate from current approved facts and validate. **Checker:** approve the new exact artifact. **Releaser:** release it and download its evidence ZIP. Inspect `release-manifest.json` and confirm PDF/file hashes. Reload the page: facts, revisions, prior decisions, stale block and release persist.

Optional failure checks: upload an image-only PDF (explicit OCR unsupported error); upload two different address lines (conflict, cannot approve); create other fixed defects; approve a new controlled template/rule version; change a source display name only (approval preserved). These must never bypass release guards.

## Two-minute spoken walkthrough

“LabelTrace answers one operational question: which exact labels can we safely release after a product-information change?

Our synthetic family has adult and pediatric tongue depressors, each with a box and carton. The labeling engineer uploads a revised adult specification. Extraction proposes facts with exact page and text-span evidence; it does not change approved product information. A separate quality reviewer accepts the evidence, and independently approves the author's change request.

The impact explorer selects the two adult labels and explains their dependencies. It also explains why the pediatric labels are unaffected. We generate actual immutable PDFs from approved facts and a versioned template, then compare artwork and individual fields.

Here we inject a barcode defect. The validator rasterizes the actual PDF and independently decodes its QR code. The wrong payload produces a blocking finding, and the release API rejects the artifact. After correction, successful validation and human approval bind to this exact revision and hash.

Now the source address changes again, without editing the approved label. The approval stays in history, but the relevant dependency becomes stale. Release is rejected. The unaffected pediatric approval remains valid.

We regenerate from the current evidence, validate, approve and release. The downloadable ZIP contains the exact PDF, facts and source versions, validation, approval history, audit events and integrity hashes. These hashes are not electronic signatures.

This is a bounded full-stack demonstration with selected US checks, deterministic extraction and optional grounded model assistance. It does not claim complete regulatory compliance, physical print-quality verification or real manufacturing integration.”
