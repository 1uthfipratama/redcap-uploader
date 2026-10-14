# Progress

## Status (2026-10-14)

Phases 1 to 5 are built; 189 tests pass. Two gate checks need people: the phase 3 trial and the phase 5 reading test (below). Next is phase 6 (Windows and macOS installers).

## Done

- **Repo set up.** It has the contributing rules (`CONTRIBUTING.md`), the PRD, `.gitignore` and LF line endings.
- **`core/grid.py`:** reads `.xls`, `.xlsx` and `.csv`. CSV encoding and delimiter are detected.
- **`core/layout.py`:** finds the title block, the merged four-row header, the official column numbers, sub-columns (RO smear/culture pairs), data rows, and blank or summary rows.
- **`tools/make_inventory.py` and the inventories.** `docs/forms/tbc03_so_*` and `tbc03_ro_*` were built from the 2020–2024 and 2025 exports of one hospital and hold structure only.
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
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
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

### Phase 5 (teaching layer)

- **`app/teaching.py`:** a "What's happening?" panel on every wizard step and every Explore tab. It is collapsed by default and written in plain Indonesian or English.
  - **Connect:** what the practice REDCap and the token are.
  - **Choose file:** how the form was recognised, where the header and data were found, and what a profile is.
  - **Preview:** how identifiers become keyed-hash pseudonyms, how many NIKs got a patient link, and why column numbers beat names.
  - **Check:** what a dry run is, an example of a spelling turned into a code, and "Tidak diketahui".
  - **Upload:** the existence check, all-or-nothing batches, "normal" overwrite, and the import-file path.
  - **Result:** how to check the records in REDCap.
  - **Explore tabs:** what each statistic means, why missing data matters, and why small groups are flagged.
- **Request log:** steps that talk to REDCap list every request, first in words, then as the actual parameters (`content=record · overwriteBehavior=normal · data=<100 records> · token=********`).
- **Plain fixes for REDCap's rejections:** `core/client.classify_problem`, with the Result table showing a "How to fix" per problem.
- **Tests:** `tests/test_teaching.py` checks the panels in both languages, the request lines, and that no label, button, table cell, panel, request log or log line holds the token or an identifier.

**Still open for the phase 5 gate:**
1. **Reading test.** Someone who has never used REDCap reads the Upload/Result panel and can say what call was made.
2. **Wording review (your call).** The privacy explanations (pseudonyms, the key) and the Indonesian phrasing should be read by you or a colleague before real users see them.

## Next: phase 6

Installers: a PyInstaller one-folder build per OS, an Inno Setup installer for Windows and a .dmg for macOS, GitHub Actions on Windows and Apple-silicon runners, a `--smoke-test` flag that runs the demo flow headlessly in CI, and a one-page researcher README in both languages.

## When the REDCap account arrives (phase 7, short version)

1. `python -m tools.export_dictionary tbc03_so out/tbc03_so_dictionary.csv`, then upload that file on the test project's Data Dictionary page.
2. Set `REDCAP_TEST_URL` and `REDCAP_TEST_TOKEN` in your own terminal, then run `pytest tests/contract`.
3. Mark each line of `docs/REDCAP_ASSUMPTIONS.md` verified or different.

## Open questions

1. **Culture result "TKM".** It appears at least 5 times in RO follow-up cultures. What does it mean? It is kept as its own code, labelled as written.
2. **"RD" in the Xpert-XDR MTB column (RO).** It appears at least 5 times. Data-entry slip for "D"? It is currently reported as an unknown spelling.
3. **Required-when rules.** The only one so far is "outcome date when an outcome is filled". Should pregnancy (women only), the child TB score (children only) or cotrimoxazole/ART (HIV positive only) be required when their condition holds?
4. **Free-text fields that are uploaded:** `occupation`, `referred_by`, `regimen_detail`, `prior_tx_detail`, `cxr_findings`, `satellite_facility` and `dst_other_*`. Patient names are unlikely there, but not impossible. Drop any of them?
5. **Quasi-identifiers.** Keep the patient district for analysis, or drop all four (current default)?
6. **SO and RO:** one REDCap project each (current default), or a single project?
