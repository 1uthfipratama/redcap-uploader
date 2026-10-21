# Progress

## Status (2026-10-21)

The tests mentioned below were removed from the repository on 2026-10-21 and are kept only on the maintainer's computer (see DECISIONS.md).

Phases 1 to 7 are built, and the wizard has five steps since the Review step replaced Preview and Check (see below). The tests pass on Windows; the contract tests passed against a REDCap 15.6.0 test project in Development status. Projects that hold real data are never used for testing. Next comes Stage 1 of [ROADMAP.md](ROADMAP.md): uploading into a project whose instruments the team designed.

## Done

- **Repo set up.** It has the contributing rules (`CONTRIBUTING.md`), the PRD, `.gitignore` and LF line endings.
- **`core/grid.py`:** reads `.xls`, `.xlsx` and `.csv`. CSV encoding and delimiter are detected.
- **`core/layout.py`:** finds the title block, the merged four-row header, the official column numbers, sub-columns (RO smear/culture pairs), data rows, and blank or summary rows.
- **`tools/make_inventory.py` and the inventories.** `synthetic/forms/tbc03_so_*` and `tbc03_ro_*` were built from the 2020–2024 and 2025 exports of one hospital and hold structure only.
- **`core/profile.py` and the profiles.** The schema has roles, choice sets with codes, rules and field-name checks. `profiles/tbc03_so.yaml` has 84 columns, 65 of them uploaded (67 REDCap fields with record_id and patient_pid); `tbc03_ro.yaml` has 144 columns, 129 uploaded (131 fields); `generic.yaml` covers Generic mode.
- **Pipeline:** `core/pipeline.py` runs parse, identifiers, mapping, normalise and validate.
  - **Identifiers** are dropped or pseudonymised right after parsing.
  - **Generic mode** matches columns by name, synonym and similarity, and drops look-alike identifier columns.
  - **Validation** checks required and required-when fields, choices, ranges, unreadable or future dates, and duplicate record IDs.
- **Messages:** `core/messages.py` with `i18n/id.json` and `en.json`. Every issue has a message and a suggested fix in both languages.
- **Test fixtures:** `synthetic/register_writer.py` writes TBC.03-shaped files from a profile, as `.xls` and `.xlsx`.
- **Tests:** 81 passing, covering:
  - the layout reader
  - profile rules
  - every identifier rule
  - every validation rule
  - normalisation
  - Generic mode
  - i18n key parity
  - end to end for SO and RO
  - privacy guards: no spreadsheets, keys or plausible NIKs in tracked files

### Phase 1b

- **REDCap behaviour, observed and assumed.** `tools/observe_pycap.py` logs what PyCap sends. `docs/REDCAP_ASSUMPTIONS.md` lists 17 assumptions, each with its source, status and test.
- **`core/dictionary.py`:** builds a profile's data dictionary, with API keys and the 18 CSV headers.
- **`mock_redcap/`:** a Flask mock on 127.0.0.1 with a random port and token. It answers version, project, metadata, exportFieldNames and formEventMapping, plus record import and export. Imports are all-or-nothing and checked against the dictionary, and blanks never erase stored values.
- **`core/client.py`:** the only module that imports PyCap. It keeps a masked request log, parses REDCap error lines, and checks URL and token so the token never appears in an error.
- **`core/upload.py`:** counts new and existing records first, then imports in batches. It stops at the first rejected batch, keeps the earlier ones, and maps each problem to its spreadsheet row.
- **`core/export_csv.py` and `tools/export_dictionary.py`:** write the dictionary CSV and an import-ready CSV for REDCap's Data Import Tool, with a checker.
- **`tests/contract/`:** one test per assumption. They run against the mock, or against a real test project when `REDCAP_TEST_URL` and `REDCAP_TEST_TOKEN` are set.
- **`tests/test_upload.py`:** the gate test. The fixture goes to the mock and back; a rejected batch stops the upload; neither the token nor any identifier appears in any log.

### Phase 2

- **`synthetic/generate.py`:** a seeded generator for TBC.03 SO (500 rows by default) and RO (100 rows). It reads only the profile and the structure-only inventory:
  - Fill rates and spellings follow the inventory, so values look like a real export ("L" and "P", "Neg").
  - Distributions are plausible but made up (`synthetic/distributions.yaml`).
  - Every identifier is obviously fake.
  - Options: `--facilities N` makes a district-style export that mixes facilities; `--year` sets the period.
- **Messy files** plant 17 defects, each listed in `<form>_defects.json` with its row, column and how it should be reported:
  - four spelling variants
  - a missing record ID and a duplicate record ID
  - age out of range
  - a mixed date format and a future date
  - an unknown spelling and a missing required field
  - two bad NIKs
  - an extra blank row
  - a changed header label
  - a summary row
  - a wrong case count (SO)
- **`synthetic/defects.py`:** checks that every planted defect was reported.
- **Gate tests:** `tests/test_synthetic.py`.

Make files with:

```bash
.venv/Scripts/python -m synthetic.generate tbc03_so --out out/synthetic
```

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m app
```

### Phase 3 (desktop UI)

- **The wizard:** `app/`, a PySide6 app in RPRI's style. Brand tokens are in `config/brand.yaml`: blue #1E6BBD, navy #002157, Rubik and DM Sans with Segoe UI as fallback.
- **The six steps:** Connect, Choose file, Preview and map, Check, Upload and Result. A step rail shows progress, Back and Next drive the flow, and a language switch in the header changes every screen at once.
- **Demo mode:** starts the built-in mock with a random token and a throwaway pseudonym key. "Or try a sample" generates a clean or messy synthetic file.
- **Real mode:** takes the URL and token (memory only) and a pseudonym key file kept outside the app folder. It checks that the project has the form's fields, and offers the dictionary CSV when it doesn't.
- **No frozen screens or stack traces:** slow work runs off the UI thread, and errors show as plain messages. The details go to a log in the user's app-data folder, without the token.
- **Tests:** `tests/test_app.py` uses pytest-qt.
  - It runs the demo end to end in both languages, plus a messy file and a Generic sheet.
  - It checks language switching, and that a bad token or unreachable server gives a plain message without echoing the token.
  - It checks that no visible text is hard-coded in `app/`.

Run it with `.venv/Scripts/python -m app`.

**Still open for the phase 3 gate:**
1. **Person trial.** Someone who has never used REDCap tries the clean sample unaided. The target is under 5 minutes.
2. **Logo and fonts (needs your OK).** The official RPRI logo goes in `app/assets/brand/logo.png`. The Rubik and DM Sans files (open licence) go in `app/assets/fonts/`. Until then, the header shows "RPRI" as text.

### Phase 4 (Explore screen)

- **`core/explore.py`:** the numbers, all tested against values worked out by hand on a tiny table.
  - Overview, variable summary, distributions, and missing data (blank and "Tidak diketahui" counted apart).
  - Group comparison and records per month.
  - Groups under 5 records are flagged.
  - Identifier and pseudonym fields are never offered.
- **`app/explore_window.py` and `app/charts.py`:** six tabs. Each has a chart, its table, and save buttons (PNG and CSV).
  - The note "summaries, not analysis results" is always visible.
  - Above `row_cap` (in `config/explore.yaml`), distributions use a seeded sample, and the screen says so.
- **Where it opens:** from the Check step once there are no errors, and from Result.
- **Speed:** a 10,000-row file shows its summary and first chart in under 3 seconds.

### Phase 5 (plain messages; the teaching panels were removed on 2026-10-21)

- **Plain fixes for REDCap's rejections:** `core/client.classify_problem`, with the Result table showing a "How to fix" per problem.
- **Tests:** `tests/test_screens.py` checks that no label, button, table cell or log line holds the token or an identifier, and that every kind of REDCap problem has a plain fix in both languages.
- **Removed:** the "What's happening?" panels (explanations and request lists) under each step and Explore tab. The app now shows what it did and found, nothing more. See DECISIONS.md.

### Phase 6 (installers)

- **`--smoke-test`:** runs the whole demo headlessly (500 records uploaded, Explore opened) and exits 0 on success. `--quit-after-start` measures start-up time.
- **`build/redcap_uploader.spec`:** a PyInstaller one-folder build for both systems, with an `.app` bundle on macOS.
- **`build/windows/installer.iss`:** Inno Setup. Installs per user by default (no administrator rights), with "all users" optional, a Start menu entry and an uninstaller.
- **`build/macos/make_dmg.sh`:** builds a .dmg with an Applications link. Signing and notarisation run only when their secrets exist.
- **`.github/workflows/ci.yml`:** tests on Linux on every push.
- **`.github/workflows/build.yml`:** builds, tests and smoke-tests the **built** package on Windows and Apple silicon. It runs only when started by hand (choose both, windows or macos) or on a `v*` tag.
- **First full run (2026-10-14):** both jobs passed. The Windows installer is 63 MB and the macOS .dmg 76 MB. On Windows 11 the window appears in about 3 s.
- **CSV fix:** the Windows job found that Python 3.12 (the build's version) guessed a semicolon CSV's delimiter wrongly. Delimiters are now chosen by a fixed rule on every version.
- **`docs/INSTALL.md`:** install guide in Indonesian and English (SmartScreen, macOS Open Anyway, Demo mode, where the log is).

Get the installers from **Actions → Build installers → Run workflow**, then download the artifacts from the finished run.

**Still open for the phase 6 gate:**
1. **Clean-machine test.** Install on a Windows PC and a Mac that have no Python, start the app, and run the demo flow in both languages.
2. **Signing (before wider rollout).** A Windows code-signing certificate and an Apple Developer account; the workflow steps are ready for their secrets.

## Real-file dry run (2026-10-15)

The four exports from one hospital (TBC.03 SO 2020–2024 and 2025, RO 2020–2024 and 2025: 6,458 records) were run through the full pipeline locally with `tools/dry_run_report.py`. Nothing was sent anywhere, and only counts were printed.

| File | Records | Read | Errors |
| --- | --- | --- | --- |
| SO 2020–2024 | 3,646 | all, form recognised | 9: 5 child TB scores above 13, 4 rare spellings |
| SO 2025 | 1,071 | all | 1 rare spelling |
| RO 2020–2024 | 1,542 | all | 31 rare spellings in lab fields (each seen fewer than 5 times) |
| RO 2025 | 199 | all | 19: 6 "RD" in the Xpert-XDR MTB column, 12 rare lab spellings, 1 blank anatomical site |

- **Layout and identifiers:** every layout matched its profile, and every NIK was valid (no precision loss). Every record got a record ID.
- **Rare spellings:** these are shown in the app's Check step on the approved machine, so a team member can add them to the profile.
- **Blocked uploads:** a single bad row currently stops the whole file at Check. For real use, an option to set rows with errors aside (listed in a report, never silently) and upload the rest may be needed. Open question 7.

## Phase 7: real REDCap check (2026-10-15)

**Result:** the contract tests pass against a REDCap 15.6.0 test project (19 of 19). Fifteen assumptions are verified, one is different (A14: REDCap saves out-of-range numbers), and three new ones were added (A18 to A20). The mock and the fix texts now follow the real server. Details in `docs/REDCAP_ASSUMPTIONS.md` and `docs/DECISIONS.md`.

**Since then:** the dictionary CSV passed REDCap's upload check (A15; the first try was not committed). The app can now add a form's missing fields to a project in Development status, and it stops when the project has a field of the same name set up differently (see DECISIONS.md). 20 of 20 contract tests pass on the real server.

**Still to check on the real server:** an import through the Data Import Tool (A16), a full upload of a synthetic file through the app in Real mode, and adding fields to a fresh project from the app.

**Data dictionary from any spreadsheet (2026-10-15).** A sheet with one header row that matches no saved form can now get a drafted data dictionary, reviewed column by column and saved as the person's own form (see DECISIONS.md). It then goes through the same checks as TBC.03 and is recognised automatically next time. To try with real REDCap: a new Development project, a spreadsheet, "Create a data dictionary", then "Add them to the project".

**How to repeat it.** On a project in Development status, with API Export, API Import/Update, Data Import Tool and Project Design rights, and an API token:

1. `python -m tools.export_dictionary tbc03_so out/tbc03_so_dictionary.csv`, then upload that file on the test project's Data Dictionary page.
2. Run `python -m tools.contract_check` in your own terminal. It asks for the API URL and the token (not shown) and runs `tests/contract`; the token stays in that process only.
3. Mark each line of `docs/REDCAP_ASSUMPTIONS.md` verified or different.

## Review step (2026-10-21)

- **One step instead of two.** Preview and map and Check are now **Review**, so the wizard is Connect, Choose file, Review, Upload, Result.
- **The table that would be sent.** Every row, one column per field, with problems, edited cells and skipped rows marked. Filters: all rows, with errors, with warnings, edited, skipped. **Go to row** and **Next problem** move around it. A row is named by its spreadsheet row number, never by an identifier.
- **Edit and skip.** **Edit value…** (or a double click) opens the cell: a list of answers for a choice field, a box for the rest, refused with REDCap's usual wording if it cannot be read. **Skip row** and **Restore row**, and **Skip all rows with errors**. The table is checked again after every change, so the errors that remain are always the ones that would block the upload.
- **Nothing is silent.** Edits and skipped rows are listed again on the Result step and written to the saved log (free-text values are left out of the log). Fields made from an identifier cannot be edited. The source file is not changed.
- **Where it lives.** `core/review.py` (no UI), `app/review_table.py` (table and edit window), `app/pages/review.py` and `review_columns.py`. 13 tests for the core and 14 for the page.
- **Faster validation.** `core/validate.py` looked up every row number cell by cell; a 3,600-row file took 3 s and now takes 0.3 s, which keeps re-checking after an edit instant.

**Not done yet:** remembering a fix in the form so next month's file passes (roadmap item 3), and a separate "rows to fix" spreadsheet (item 4). Check the wording of the new screens in Indonesian.

## Tutorial, diagrams and wording (2026-10-21)

- **Tutorial tab** next to Upload. Eight annotated screenshots (connect, connect to your project, choose a file, review, edit, ready, upload, result) with numbered highlights on what to press, and seven notes under "How it works": overview, how identifiers are found, pseudonyms and the key, what is checked, records and batches, edit and skip, setting up a project. English and Indonesian. `python -m tools.make_tutorial` makes the pictures from the running app with synthetic data and a fixed demo key.
- **Diagrams** (`docs/pipeline.svg`, `identifiers.svg`, `lifecycle.svg`) are drawn from one source, `app/diagrams.py`, in both languages. The README and PRD use the English files; a test fails when they are out of date.
- **General wording.** The page lead lines are gone, the status lines on Review are one line, and the README, PRD, CONTRIBUTING and roadmap no longer present the app as a SITB tool. TBC.03 SO and RO are bundled forms, shown as examples.
- **Radio buttons** now show which is selected (a filled dot in the brand blue). Before, the selected one looked unselected in Windows.
- Check the Indonesian text of the tutorial and the diagrams.

## Receipt and readiness check (2026-10-21)

- **Receipt.** **Save receipt** on the Result step writes a CSV: every row of the file, the record ID it became, created, updated, rejected, not sent or skipped (by you, or for errors), the batch, and the names of the fields edited. `core/receipt.py`; the upload plan now keeps the list of records it will update. Tests: 4 for the core and one for the button.
- **Readiness check.** After Connect a table says Development or Production, the record ID field, events, repeating instruments and the record count, with what to do about any problem. `core/readiness.py`; the mock can now play a Production, longitudinal or repeating project. Tests: 11 for the core and the table. A new assumption, A21, is unverified on a real server.
- The tutorial has a "Check the project" step and its Result step shows both buttons; screenshots were made again.

## Open questions

1. **Culture result "TKM".** It appears at least 5 times in RO follow-up cultures. What does it mean? It is kept as its own code, labelled as written.
2. **"RD" in the Xpert-XDR MTB column (RO).** It appears at least 5 times. Data-entry slip for "D"? It is currently reported as an unknown spelling.
3. **Required-when rules.** The only one so far is "outcome date when an outcome is filled". Should pregnancy (women only), the child TB score (children only) or cotrimoxazole/ART (HIV positive only) be required when their condition holds?
4. **Free-text fields that are uploaded:** `occupation`, `referred_by`, `regimen_detail`, `prior_tx_detail`, `cxr_findings`, `satellite_facility` and `dst_other_*`. Patient names are unlikely there, but not impossible. Drop any of them?
5. **Quasi-identifiers.** Keep the patient district for analysis, or drop all four (current default)?
6. **SO and RO:** one REDCap project each (current default), or a single project? A single project would need `regimen_cat` and `dm_screen` renamed in one of the profiles, since they mean different things in the two forms.
7. **Rows with errors:** answered on 2026-10-21. Errors still block the upload, but a row can be fixed or skipped on the Review step, and every skip is listed.
