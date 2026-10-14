# Progress

## Status (2026-10-14)

Phase 1a (profiles and core pipeline) passes its gate. Next is phase 1b (mock REDCap, client and upload).

## Done

- **Repo set up.** It has the contributing rules (`CONTRIBUTING.md`), the PRD, `.gitignore` and LF line endings.
- **`core/grid.py`:** reads `.xls`, `.xlsx` and `.csv`. CSV encoding and delimiter are detected.
- **`core/layout.py`:** finds the title block, the merged four-row header, the official column numbers, sub-columns (RO smear/culture pairs), data rows, and blank or summary rows.
- **`tools/make_inventory.py` and the inventories.** `docs/forms/tbc03_so_*` and `tbc03_ro_*` were built from the 2020–2024 and 2025 exports of one hospital and hold structure only.
- **`core/profile.py` and the profiles.** The schema has roles, choice sets with codes, rules and field-name checks. `profiles/tbc03_so.yaml` has 84 columns, 61 of them uploaded; `tbc03_ro.yaml` has 144 columns, 125 uploaded; `generic.yaml` covers Generic mode.
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

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

## Next: phase 1b

`docs/REDCAP_ASSUMPTIONS.md`, the Flask mock, `core/client.py`, `core/upload.py`, `core/export_csv.py`, and `tests/contract/`. See `docs/PRD.md` (Milestones).

## Open questions

1. **Culture result "TKM".** It appears at least 5 times in RO follow-up cultures. What does it mean? It is kept as its own code, labelled as written.
2. **"RD" in the Xpert-XDR MTB column (RO).** It appears at least 5 times. Data-entry slip for "D"? It is currently reported as an unknown spelling.
3. **Required-when rules.** The only one so far is "outcome date when an outcome is filled". Should pregnancy (women only), the child TB score (children only) or cotrimoxazole/ART (HIV positive only) be required when their condition holds?
4. **Free-text fields that are uploaded:** `occupation`, `referred_by`, `regimen_detail`, `prior_tx_detail`, `cxr_findings`, `satellite_facility` and `dst_other_*`. Patient names are unlikely there, but not impossible. Drop any of them?
5. **Quasi-identifiers.** Keep the patient district for analysis, or drop all four (current default)?
6. **SO and RO:** one REDCap project each (current default), or a single project?
