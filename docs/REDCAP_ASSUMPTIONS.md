# REDCap assumptions

There is no REDCap account yet. Every behaviour of real REDCap that the app relies on is listed here, with its source and status:
- **observed:** seen in what PyCap sends (`python -m tools.observe_pycap`). This describes the client, not the server.
- **unverified:** what we believe REDCap does, from its API documentation or common knowledge. The mock behaves this way until phase 7 checks it.
- **verified** or **different:** set in phase 7, against a real test project.

Each line has a contract test in `tests/contract/`. The tests run against the mock by default, and against a real project when `REDCAP_TEST_URL` and `REDCAP_TEST_TOKEN` are set.

| ID | Assumption | Source | Status | Test |
| --- | --- | --- | --- | --- |
| A01 | Creating a PyCap `Project` sends no request; calls happen on first use. | PyCap 2.7.0, observed | observed | — |
| A02 | Connect needs `content=version`, `content=project` (format json) and `content=metadata` (format json). | PyCap 2.7.0, observed | observed | `test_connect` |
| A03 | `is_longitudinal` sends `content=formEventMapping`. A classic project answers with an error, which PyCap reads as "not longitudinal". | PyCap observed; REDCap behaviour unverified | unverified | `test_classic_project_is_not_longitudinal` |
| A04 | Record import is `content=record`, `format=json`, `type=flat`, with `data`, `overwriteBehavior`, `returnContent`, `dateFormat=YMD`, `forceAutoNumber` and `returnFormat=json`. It has no `action` parameter. | PyCap 2.7.0, observed | observed | `test_import_counts` |
| A05 | Record export is `content=record`, `type=flat`, `rawOrLabel=raw`, with every field listed as `fields[n]`. With no fields given, PyCap lists them all from the dictionary, plus `<form>_complete`. | PyCap 2.7.0, observed | observed | `test_export_round_trip` |
| A06 | Import is all-or-nothing per request: one invalid record rejects the whole batch, and nothing in it is saved. | REDCap API docs (record import) | unverified | `test_bad_batch_imports_nothing` |
| A07 | An import error is JSON `{"error": "..."}`, and PyCap raises `RedcapError` for it. Each problem is one line: `"record","field","value","message"`. | REDCap API behaviour as commonly reported | unverified | `test_error_names_record_field_value` |
| A08 | Dates are imported as `YYYY-MM-DD` when `dateFormat=YMD`; other formats are rejected for date-validated fields. | REDCap API docs | unverified | `test_date_must_be_ymd` |
| A09 | Radio and dropdown fields accept only the raw codes in the dictionary, not the labels. | REDCap data dictionary rules | unverified | `test_label_instead_of_code_is_rejected` |
| A10 | With `overwriteBehavior=normal`, a blank value does not erase a stored value. | REDCap API docs | unverified | `test_blank_does_not_erase` |
| A11 | Importing a record whose ID already exists updates it; it does not create a second record. | REDCap behaviour | unverified | `test_reimport_updates` |
| A12 | `returnContent=count` returns `{"count": n}`; `returnContent=ids` returns a list of the record IDs saved. | REDCap API docs | unverified | `test_import_counts` |
| A13 | A field name that is not in the dictionary is an error. | REDCap behaviour | unverified | `test_unknown_field_is_rejected` |
| A14 | Number and integer fields with min and max reject values outside the range. | REDCap behaviour (range checks are hard errors in API import) | unverified | `test_out_of_range_is_rejected` |
| A15 | The data dictionary CSV for upload has these 18 columns, in this order: Variable / Field Name, Form Name, Section Header, Field Type, Field Label, Choices Calculations OR Slider Labels, Field Note, Text Validation Type OR Show Slider Number, Text Validation Min, Text Validation Max, Identifier?, Branching Logic, Required Field?, Custom Alignment, Question Number, Matrix Group Name, Matrix Ranking?, Field Annotation. | REDCap data dictionary template | unverified | `test_dictionary_csv_columns` |
| A16 | A Data Import Tool CSV has one row per record, the record ID column first, raw codes, and dates as `YYYY-MM-DD`. | REDCap Data Import Tool template | unverified | `test_import_csv_matches_dictionary` |
| A17 | A wrong token gets an error, not data. | REDCap behaviour | unverified | `test_bad_token_is_refused` |

When the mock and this table disagree, fix one of them and record why in `docs/DECISIONS.md`.
