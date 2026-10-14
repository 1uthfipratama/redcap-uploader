# Decisions

Each entry says what was decided, why, and when to revisit it. Newest at the bottom.

## 2026-10-14 · Phase 1a

**Record ID source.** `record_id` is a keyed hash of the form code and *Nomor Register Pasien*, column (9) in SO and (11) in RO. In the 2020–2025 exports this column is filled and unique on every row, so one row is one episode. *Nomor Register SITB* repeats across a patient's episodes (98% unique in SO, 91% in RO). It is pseudonymised as `sitb_pid`, a second patient link next to `patient_pid` (from the NIK). Revisit if the protocol defines the study ID differently.

**Pseudonyms.** HMAC-SHA256 with a project key from the environment or a key file outside the repo. Truncated to 16 hex characters (64 bits). The purpose is part of the message (`record`, `patient`, or the field name), so the same source value gives different pseudonyms in different roles. Collisions between different source values are checked and reported as errors. There is no default key.

**NIK cleaning.** The exports store NIKs as numbers. Excel keeps whole numbers exactly only below 2^53 (about 9.0 × 10^15). A NIK stored as a larger float may have lost digits, so it is rejected as `precision_lost`. Province codes 91–94 (Papua) fall in that range. Scientific notation, blanks, wrong length and all-zero values are also rejected. A rejected NIK gets no `patient_pid` and is counted, but the row is still uploaded.

**One REDCap project per form.** The SO and RO profiles share field names (`age`, `sex`, `outcome` and others), and REDCap needs unique field names within a project. Revisit if the study wants SO and RO in one project: prefix the RO fields, or move to an instrument per form.

**Choice codes.** These conventions hold across profiles:
- yes = 1, no = 0, unknown ("Tidak diketahui") = 99, not done ("TDL") = 98.
- Microscopy: negative = 0, scanty counts 1–9 keep their number, 1+ = 11, 2+ = 12, 3+ = 13.
- Other sets are numbered in the order the form lists them.

**Value maps merge spellings, not meanings.** A map merges only case and spacing variants ("Neg", "NEG"), the form's own abbreviations ("L" and "P" for sex) and documented synonyms ("Tidak Tahu" for "Tidak diketahui"). Different results stay different codes. Long result strings stay text fields, because their combinations are open-ended:
- the diagnostic test result
- the RO chest X-ray findings
- regimen details
- "other drug" DST cells

**Mixed date formats are errors.** A date that does not match the profile's format (dd/mm/yyyy) is reported with its row and field. It is not quietly read as another format.

**Spellings in the inventories.** Only spellings seen at least 5 times are listed, and never for identifier or quasi-identifier columns. Rarer spellings are counted, not shown. At runtime they show up as "spelling not in profile", so the profile can be extended from real use.

**Generic mode.** Headers that look like identifiers are dropped right after parsing and never uploaded. Patterns cover NIK, name, address, BPJS, phone, email, medical record number and date of birth (see `config/generic_mapping.yaml`). Name matching uses exact names, a synonym list, then similarity of at least 0.75, with the score shown.

## 2026-10-14 · Phase 1b

**Mock framework: Flask** (served by werkzeug's threaded server on 127.0.0.1 and a random port). It is small, synchronous and bundles cleanly with PyInstaller. FastAPI would add uvicorn and async for no gain. Each run gets a fresh random 32-character token, so the demo has no fixed credential.

**The client checks URL and token itself.** If a token has the wrong length, PyCap 2.7.0 raises an assertion whose message quotes the token. `core/client.py` checks the URL shape (http(s), ending in `/api/`) and the token shape (32 alphanumeric characters) before PyCap sees them. It also turns any PyCap assertion into `InvalidSettings("token")`, with no value in it. PyCap's `RedcapError` is just `requests.RequestException`, so connection failures are caught first and reported separately (`ConnectionFailed`).

**Uploads stop at the first rejected batch.** Imports are all-or-nothing per request (assumption A06). When a batch is rejected, the upload stops: earlier batches stay imported, and later batches are not sent. The result names every problem by record, field, value and spreadsheet row. Retrying after a fix is safe, because re-importing a record updates it (A11) and blanks never erase stored values (A10).

**Pseudonym fields are flagged as identifiers in the dictionary.** `patient_pid` and `sitb_pid` are marked `Identifier? = y`, so REDCap's de-identified exports leave them out. `record_id` cannot be flagged.

**Request log.** Every API call is kept in `RedcapClient.log` for the teaching panels. The token is replaced by `********` and record data by a count (`<5 records>`). Error text is kept: it contains REDCap's lines of record, field, value and message, which hold pseudonyms and coded values, never raw identifiers.
