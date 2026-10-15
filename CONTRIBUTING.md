# Contributing: REDCap Uploader

Read this fully before writing or changing code. If a request conflicts with this file, stop and ask.

## 1. What this is
- A universal tool for any researcher or TB programme team that works with SITB exports, at any facility, district or province. It is not tied to one study or site.
- A desktop app for Windows and macOS (PySide6) that guides a researcher through uploading a spreadsheet to REDCap: connect, choose file and form, preview and map, validate (dry run), upload, result.
- Two ways out: direct API import (PyCap), or an import-ready CSV plus the matching data dictionary for REDCap's Data Import Tool when API access is not available.
- Form-agnostic: every source form is a form profile (YAML). TBC.03 SO and TBC.03 RO from the Indonesian TB register (SITB) ship first; a Generic profile reads any single-header sheet. A new form must need a new profile, never new code.
- After cleaning, an Explore screen shows descriptive statistics and charts.
- A teaching tool: every step has a "What's happening?" panel showing the real API call, token masked.
- Stage 1 (now): prototype on synthetic data against an embedded mock REDCap. Every assumption about real REDCap is written down and checked against a real test project (section 8); phase 7 did this on REDCap 15.6.0. Stage 2 (later): production use on real SITB extracts by any team, each after its own ethics approval, data-governance sign-off and REDCap project. The TBestie LTFU study is the first user.
- UI languages: Bahasa Indonesia and English from the first release.

## 2. Hard rules
1. No patient-identifying data in the repo, tests, logs, screenshots or fixtures: no NIK, names, addresses, BPJS or record numbers, and no raw SITB exports. Real files live outside the repo folder. Besides the app itself, only tools/make_inventory.py and tools/dry_run_report.py open a real export, and they print structure and counts only.
2. Identifiers are handled right after parsing, per the profile: dropped, or pseudonymised with a keyed hash (HMAC-SHA256). The key is never in the repo. Raw identifiers never reach logs, charts, error messages or the REDCap client.
3. record_id is episode-level: a keyed hash of the form, the facility code and the patient register number, so one patient can have several records. patient_pid, a keyed hash of the cleaned NIK, links a patient's episodes.
4. NIKs are cleaned before hashing: digits only, exactly 16, no scientific notation or leading apostrophe. A blank or invalid NIK never gets a pseudonym; it is reported with a count.
5. The API token is never written to a file, log or error message. Memory only; OS keyring only if the user opts in.
6. core/ has no UI imports. The UI never imports PyCap; only core/client.py does.
7. Switching Demo to Real changes only the URL and token.
8. Values sent to REDCap are choice codes, never labels. Each value map goes from source spelling to a REDCap code.
9. "Tidak diketahui" (unknown) is its own category with its own code; never recode it to "no" or blank. Spellings not in the map are reported, never guessed.
10. Never drop rows silently. Every skipped, excluded or rejected row is reported with a reason and a count.
11. Uploads use overwriteBehavior=normal, so a blank cell never erases a value already in REDCap.
12. The Explore screen is descriptive only: no p-values, tests or models.
13. Do not add features outside the PRD without asking.
14. Universal by design: no facility, region, study or institution is hard-coded in code or profiles. Facility details come from the file. Each team brings its own pseudonym key, REDCap project and settings.
15. No secrets in the repo: no API tokens, pseudonym keys, certificates or passwords, in any file or commit message. Signing secrets live only in GitHub's encrypted secrets. A test fails on anything token- or key-shaped.

## 3. Stack
Python 3.10+, PySide6, pandas, openpyxl, xlrd (legacy .xls), pydantic and PyYAML (profiles), PyCap, Flask for the mock (small, synchronous, bundles cleanly with PyInstaller), matplotlib with the Qt backend (import lazily), pytest and pytest-qt, PyInstaller (one-folder), Inno Setup (Windows), a .dmg (macOS), GitHub Actions. Dev-only: xlwt, to write .xls test fixtures.

## 4. Repo layout
  app/           PySide6 wizard, step screens, Explore screen, teaching panels
  core/          grid, layout, profile, parse, identifiers, mapping, normalise, validate, pipeline, dictionary, client, project_setup, upload, export_csv, explore (no UI imports)
  profiles/      tbc03_so.yaml, tbc03_ro.yaml, generic.yaml
  mock_redcap/   embedded Flask mock; its data dictionary is generated from the selected profile
  synthetic/     generators that reproduce the TBC.03 layouts with fake values
  tools/         make_inventory.py (structure-only column inventory), dry_run_report.py (aggregate-only dry run of a real export), observe_pycap.py, export_dictionary.py, contract_check.py (runs tests/contract against a real test project)
  i18n/          id.json, en.json
  config/        settings, redcap_target.yaml
  tests/         unit tests; tests/contract/ runs against the mock or a real test project
  build/         PyInstaller specs; Inno Setup (Windows); dmg and signing scripts (macOS)
  .github/       CI that builds on Windows and macOS runners
  docs/          PRD.md, PROGRESS.md, DECISIONS.md, REDCAP_ASSUMPTIONS.md, forms/ (structure-only column inventories)

## 5. What the real SITB files look like (structure only)
- docs/forms/tbc03_so_columns.csv and tbc03_ro_columns.csv list every column: official number, flattened header, type, fill rate, suggested role, and the spellings seen in low-cardinality columns. Build the profiles from these. Do not ask for the real exports. They come from one facility's exports (2020 to 2025). Other facilities, district-level exports and later SITB editions may add spellings or columns: unknown spellings are reported, and layout differences block reading with a clear message.
- Each file starts with a title block (form name, edition, facility, period; SO also states the case count, "Jumlah Kasus"), then a four-row merged header (Excel rows 13 to 16), a row of official column numbers in brackets such as (39) (row 17), the data rows from row 18, and one trailing blank row. The exports have no summary row at the bottom; the reader still skips one if present. Use the official numbers as stable keys (c039, or c083_bta for a sub-column), not the labels.
- Dates are usually text (dd/mm/yyyy); accept real Excel date cells too. The exports are legacy .xls.
- SO has 84 numbered columns. RO has 114 numbers, some covering a smear and culture pair (144 sheet columns). Value sets differ between the two forms.
- Identifier columns: NIK, name, full address, BPJS, record and registration numbers, lab registration numbers. Patient province, district, subdistrict and village are quasi-identifiers: drop them unless the profile says keep.
- NIK and register numbers are stored as numbers in the exports, so they can lose digits; treat any NIK that is not 16 digits as invalid.
- Nomor Register Pasien is filled and unique on every row: it is the record_id source. Nomor Register SITB repeats across a patient's episodes and is pseudonymised as sitb_pid.
- RO follow-up months 1 to 24 import as plain wide fields first (smear_m1 to smear_m24, culture_m1 to culture_m24; months 4 to 6 also have smear2_mN and culture2_mN).

## 6. Wizard steps
1. Connect: Demo or Real; shows the project name and REDCap version.
2. Choose file and form: CSV, XLSX or XLS; recognise the form or fall back to Generic; read the merged header; skip title and summary rows. Stop if the project has a field of the same name set up differently; if fields are missing, offer to add them (Development only, never removing any) or to save the dictionary.
3. Preview and map: match by official column number (name similarity in Generic mode); show which columns will be dropped or pseudonymised.
4. Validate (dry run): apply value maps, then check required fields, choices, ranges, date formats, duplicate IDs. Nothing is sent.
5. Upload: first export existing record IDs and show new and existing counts; then import_records in batches with progress. Or save the import-ready CSV instead.
6. Result: imported and rejected counts with reasons; downloadable log.
Explore opens from step 4 once validation passes, and from step 6.

## 7. Mock server
- Speaks the same HTTP API PyCap uses (POST with a content parameter) on 127.0.0.1 and a random free port.
- Observe which calls PyCap makes on connect, import and export, and implement exactly those; do not guess. Cover version, project info, data dictionary (metadata), field names, record import and record export.
- Imports are all-or-nothing per request, as REDCap does: one invalid record rejects the whole batch, with an error naming record, field and value.
- Validates against the data dictionary as real REDCap does: choice codes, integer and number formats, dates as YYYY-MM-DD, unknown fields. Like REDCap, it does not enforce min and max or reject future dates (A14, A20); the app's Check step does.
- Behaviour follows docs/REDCAP_ASSUMPTIONS.md; when the two disagree, fix one and log it.

## 8. REDCap assumptions
- docs/REDCAP_ASSUMPTIONS.md lists every behaviour of real REDCap the app depends on, with its source (API docs, PyCap source) and status: unverified, verified or different. Add a line whenever code relies on a new one.
- tests/contract/ checks each assumption. It runs against the mock by default and against a real test project with python -m tools.contract_check (or when REDCAP_TEST_URL and REDCAP_TEST_TOKEN are set in the environment).
- Target settings live in config/redcap_target.yaml with best-case defaults: classic project (not longitudinal), no repeating instruments, no DAGs, record ID field record_id, dates sent as YYYY-MM-DD, overwriteBehavior normal, batch size 100.

## 9. Explore screen
Data overview, variable summary, distributions, missingness, group comparison, records over time. All numbers come from core/explore; the UI only draws them. Identifier fields never appear in field pickers. Every chart saves as PNG and every table as CSV. Groups under 5 records are flagged.

## 10. Conventions
- All user-facing text lives in i18n/id.json and i18n/en.json; no hard-coded strings in app/. A test checks both files have the same keys.
- Every random process takes a seed. Settings live in config files, not code.
- Small, documented functions. Prefer clarity over cleverness; clinicians and statisticians will read this.
- Tests cover: layout reader, mapping, each validation rule, normalisation, identifier handling, explore calculations, the contract suite, and that the token and raw identifiers never appear in logs.
- After each phase, update docs/PROGRESS.md: what is done, what is next, open questions.

## 11. Open decisions (ask, do not assume)
Intel Mac build; ethics and data-governance status for stage 2; which forms come after TBC.03; repeating instruments for RO follow-up; who holds the pseudonym key; REDCap API access policy, version and project status at the institution; whether Nomor Register Pasien is unique nationally (record_id includes the facility code until this is known).
