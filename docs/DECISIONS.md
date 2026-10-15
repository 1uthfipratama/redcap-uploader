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

## 2026-10-14 · Universal use

**For any SITB user, not one site.** No facility, region or study is hard-coded. Facility, district and province come from each row, so exports at district or province level, which mix facilities, work too. Each team uses its own pseudonym key and REDCap project.

**Facility columns are data.** The six facility-address columns are uploaded (`fasyankes_province`, `fasyankes_district`, `fasyankes_type`, `fasyankes_ownership`, `fasyankes_code`, `fasyankes_name`), not treated as constant. Facility details are not patient identifiers.

**record_id includes the facility code.** It is now a keyed hash of the form, the facility code (`record_id_scope` in the profile) and Nomor Register Pasien. It is not yet known whether that number is unique nationally. If it is not, two facilities could share a number and their patients would be merged into one record, silently. Including the facility code means the worst case is the opposite: one episode exported under two facility codes would give two records, which is visible and easy to fix. Revisit once SITB's numbering is confirmed.

## 2026-10-14 · Phase 2

**Planted defects follow the real files.** The plan listed "a missing summary row" as a defect, but the real exports have no summary row. The messy file plants the two cases that can actually happen instead:
- an unexpected summary row, which is skipped and counted;
- a case count in the title block that does not match the rows read (SO only).

**Synthetic values use the real spellings.** For each choice, the generator writes the spelling the inventory shows most often (for example "L", not "Laki-laki"). Clean files therefore exercise the same value maps that real files do. Weights for key fields are in `synthetic/distributions.yaml` and are made up; nothing comes from patient-level data.

**No outcome dates after today.** A synthetic outcome whose date would fall after today is left blank, as for a patient still on treatment. Clean files therefore always pass the "date in the future" check.

## 2026-10-14 · Phase 3

**RPRI's look, with few colours.** One blue for actions and the current step, navy for headings, and white panels on a pale canvas. There are no badges or status pills. Errors and successes are shown as a coloured headline line, not as banners.

**"Check" instead of "Validate"** in the step names. It is the plainer word in both languages ("Periksa").

**Demo mode uses a fresh random pseudonym key** each session. Demo mode only ever handles synthetic files, so there is nothing to link across sessions, and no key ever needs to be stored.

**Real mode checks the project before reading the file.** If the REDCap project lacks fields the form uploads, the app stops at Choose file. It names the missing fields and offers the data dictionary CSV to set the project up, instead of failing later with a server error on every batch.

**An unreadable value is reported once.** A required date that cannot be read used to appear twice: as "not a date" and as "required but empty". Now only the first is shown.

## 2026-10-14 · Phase 4

**Explore opens in its own window.** That lets the wizard stay where it was, and matplotlib loads only when someone opens Explore, which keeps the app quick to start.

**One chart look, checked for colour blindness.** Series 1 is the brand blue. Series 2 to 4 follow the reference order (orange, aqua, yellow). The set passes the colour-blindness validator: worst adjacent pair ΔE 9.1. Two of these colours are low-contrast on white, so every chart has its table beside it, and categorical shares show at most four named answers plus "other". "Unknown", "blank" and "other" are grey, because they are context, not data.

**Histogram bins sit on round numbers** (widths of 1, 2, 2.5 or 5 times a power of ten). An age chart therefore reads 0–5, 5–10, and not 0–4.2.

**The SD is the sample SD** (n−1). A group with one value has no SD rather than 0.

**No hover tooltips in charts.** In a desktop app, the table next to each chart is the reliable way to read exact values. Tooltips can come later if users ask for them.

## 2026-10-14 · Explore readability pass

**Every chart has a title, a one-row legend under it, and room to breathe.** Saved PNGs are self-explaining. Legends never sit on the data or the axis label. Long category labels wrap. Count axes use whole numbers. Horizontal charts get taller as rows are added, instead of squeezing bars.

**Answer comparisons are grouped bars with every answer shown.** The first version stacked four named answers and folded the rest into "other". That hid "lost to follow-up", the outcome this tool's first study cares about most. Now each answer is a row with one bar per group. Up to four groups are drawn, each in its own validated colour, and the table always lists all groups.

**Blanks stay out of distribution charts.** A field that is 90% blank used to squeeze every real answer into slivers. Blanks are now a note under the chart and a row in the table. Percentages are shares of answered records, and the table also gives the share of all records.

**The Variables table shows a one-line summary.** On screen it has eight readable columns ("mean 41.3 (SD 20.8) · median 41 (Q1–Q3 26–53) · range 0–85"). The saved CSV keeps every statistic in its own column.

**Tables fit their content.** Numbers are right-aligned, and only free-text columns stretch. A table is as tall as its rows, up to 12, and then scrolls. Each save button sits next to the chart or table it saves.

## 2026-10-14 · Phase 5

**Explanations are collapsed by default.** The panel sits under each step's work and opens with one click, so first-time users can learn and regular users aren't slowed down.

**Each request is shown twice: in words, then as the real parameters.** The words ("Sent 100 records to be saved (overwrite: normal)") are for people new to REDCap. The parameter line is for anyone who wants to see the real API call. Both come from `RedcapClient.log`, which already masks the token and turns record data into a count. The panel therefore cannot show anything secret, and a test checks this.

**REDCap's own messages stay as they are, with a plain fix beside them.** Rewriting the server's words risks losing detail. Instead each message is matched to a kind of problem (category, date, range, number, unknown field, record ID, permission, other), and the "How to fix" column explains that kind. The patterns are an assumption about REDCap's wording, to be checked in phase 7 (A07).

**The privacy wording describes what the app does, and makes no promises.** For example: the code "cannot be turned back into the NIK without the key." It never claims the data is anonymous: pseudonymised data can still be personal data under data-protection rules.

## 2026-10-14 · Phase 6

**One-folder builds, not single files.** A single-file executable has to unpack itself to a temporary folder every time it starts, which is slower, and antivirus tools often flag it. The installer and the .dmg wrap a one-folder build instead.

**Per-user install on Windows by default.** Hospital and university computers often deny administrator rights. The installer therefore installs to the user's own programs folder by default, and offers "all users" (Program Files) when an administrator runs it.

**Measured.** On Windows 11 (local build, Python 3.13, PySide6 6.12) the app folder is 207 MB, the window appears in about 3.0 s, and the full demo smoke test (500 records) passes in about 5 s. On the first CI run (Python 3.12) the Windows installer was 63 MB and the macOS .dmg 76 MB, and the macOS smoke test passed in 16 s on the Apple-silicon runner. Later runs write sizes and start-up times into each run's summary.

**The build runs only by hand or on a version tag.** On a private repository, GitHub counts macOS minutes ten times and Windows minutes twice against the free allowance. Tests run on Linux, the cheapest runner, on every push.

**Signing waits for certificates.** Both workflows sign and notarise only when the secrets exist, and skip cleanly otherwise. Until then, docs/INSTALL.md explains the SmartScreen "Run anyway" and the macOS "Open Anyway" steps. A Windows code-signing certificate and an Apple Developer account (99 USD a year) are needed before wider rollout.

**Apple silicon only on macOS for now** (the macos-14 runner). An Intel build needs a second runner or a universal build. That is still the open decision about Intel Macs.

## 2026-10-15 · Phase 7 (real REDCap check)

**Checked on a real server.** The contract tests ran against a REDCap 15.6.0 test project (classic, Development status, the TBC.03 SO dictionary). 19 of 19 pass after the changes below. See `docs/REDCAP_ASSUMPTIONS.md`.

**REDCap does not enforce min and max on import (A14, different).** An age of 212 or -1 is saved. The same holds for dates in the future (A20). So the app's own checks are the only gate: out-of-range values and future dates stay errors that block the upload at the Check step. The mock no longer rejects them, so it behaves like the real server, and the "outside the range" fix text was removed because REDCap never sends it.

**The mock uses REDCap's own wording** for wrong formats, bad dates and a wrong token, so the fix texts the app shows are tested against real messages. A wrong token is answered in XML whatever format was asked for (A17); the client reads the message out of it instead of showing the XML.

**Dictionary upload through the API works in Development (A18).** The first upload of the dictionary on the Data Dictionary page did not reach the project, so it was imported through the API instead (67 fields). That is the mechanism for the planned "add the missing fields to the project" feature. The import replaces the whole dictionary, so the feature must merge with what the project already has and never remove fields.

## 2026-10-15 · Adding a form's fields to a project

**The app can add the missing fields itself.** When the project lacks fields the form needs, the Choose step offers "Add them to the project" next to "Save data dictionary…". It is offered only for a project in Development status whose record ID field is `record_id`; in production the dictionary file goes to the REDCap administrator instead. The person confirms first.

**Add, never remove.** A dictionary import replaces the whole dictionary (A18), so the app downloads the current one, keeps every field unchanged and in order, and appends only the missing ones. A fresh project (only its record ID field) takes the form's dictionary as it is, so REDCap's default instrument disappears. The current dictionary is saved first, to Documents/REDCap Uploader/Dictionary backups.

**Same name, different setup, stops the upload.** TBC.03 SO and RO share 53 field names, and two of them differ: `regimen_cat` (code 1 is "Kategori 1" in SO but "Paduan Jangka Pendek" in RO) and `dm_screen` (Positif/Negatif against Ya/Tidak). REDCap would accept the codes and store the wrong meaning. So before reading the file, the app compares every shared field's type, answer list and format with the project, and stops with the field names when any differ. Min and max are not compared, because REDCap does not enforce them. This also means SO and RO cannot share one project with the current field names (open question 6).

