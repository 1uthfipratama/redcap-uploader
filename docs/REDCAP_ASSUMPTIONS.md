# REDCap assumptions

Every behaviour of real REDCap that the app relies on is listed here, with its source and status:
- **observed:** seen in what PyCap sends (`python -m tools.observe_pycap`). This describes the client, not the server.
- **unverified:** what we believe REDCap does, from its API documentation or common knowledge. The mock behaves this way until it is checked.
- **verified** or **different:** checked against a real test project. Phase 7 (2026-10-15) ran the contract tests on REDCap 15.6.0, on a classic project in Development status with the TBC.03 SO dictionary.

Each line has a contract test in `tests/contract/`. The tests run against the mock by default, and against a real project with `python -m tools.contract_check`.

| ID | Assumption | Source | Status | Test |
| --- | --- | --- | --- | --- |
| A01 | Creating a PyCap `Project` sends no request; calls happen on first use. | PyCap 2.7.0, observed | observed | — |
| A02 | Connect needs `content=version`, `content=project` (format json) and `content=metadata` (format json). | PyCap 2.7.0, observed | verified | `test_connect` |
| A03 | `is_longitudinal` sends `content=formEventMapping`. A classic project answers with an error, which PyCap reads as "not longitudinal". | PyCap observed; REDCap 15.6.0 | verified | `test_classic_project_is_not_longitudinal` |
| A04 | Record import is `content=record`, `format=json`, `type=flat`, with `data`, `overwriteBehavior`, `returnContent`, `dateFormat=YMD`, `forceAutoNumber` and `returnFormat=json`. It has no `action` parameter. | PyCap 2.7.0, observed | verified | `test_import_counts` |
| A05 | Record export is `content=record`, `type=flat`, `rawOrLabel=raw`, with every field listed as `fields[n]`. With no fields given, PyCap lists them all from the dictionary, plus `<form>_complete`. | PyCap 2.7.0, observed | verified | `test_export_round_trip` |
| A06 | Import is all-or-nothing per request: one invalid record rejects the whole batch, and nothing in it is saved. | REDCap 15.6.0 | verified | `test_bad_batch_imports_nothing` |
| A07 | An import error is JSON `{"error": "..."}`, and PyCap raises `RedcapError` for it. Each problem is one line: `"record","field","value","message"`, and every problem in the batch is listed. Unknown fields are the exception: one plain message (A13). | REDCap 15.6.0 | verified | `test_error_names_record_field_value` |
| A08 | Dates are imported as `YYYY-MM-DD` when `dateFormat=YMD`; other formats and impossible dates (30 February) are rejected with "Invalid date format. (NOTE: Dates must be imported here only in Y-M-D format, ...)". | REDCap 15.6.0 | verified | `test_date_must_be_ymd` |
| A09 | Radio and dropdown fields accept only the raw codes in the dictionary, not the labels: "The value is not a valid category for <field>". | REDCap 15.6.0 | verified | `test_label_instead_of_code_is_rejected` |
| A10 | With `overwriteBehavior=normal`, a blank value does not erase a stored value. | REDCap 15.6.0 | verified | `test_blank_does_not_erase` |
| A11 | Importing a record whose ID already exists updates it; it does not create a second record. | REDCap 15.6.0 | verified | `test_reimport_updates` |
| A12 | `returnContent=ids` returns a list of the record IDs saved. (`returnContent=count`, not used by the app, is not checked.) | REDCap 15.6.0 | verified | `test_import_counts` |
| A13 | A field name that is not in the dictionary rejects the batch with one plain message: "The following fields were not found in the project as real data fields: a, b". | REDCap 15.6.0 | verified | `test_unknown_field_is_rejected` |
| A14 | **Different.** Min and max on integer and number fields are *not* enforced on import: out-of-range values (an age of 212 or -1) are saved. The app's own range check is the only gate, so out-of-range values block the upload at the Check step. | REDCap 15.6.0 | different | `test_out_of_range_is_saved` |
| A15 | The data dictionary CSV for upload has these 18 columns, in this order: Variable / Field Name, Form Name, Section Header, Field Type, Field Label, Choices Calculations OR Slider Labels, Field Note, Text Validation Type OR Show Slider Number, Text Validation Min, Text Validation Max, Identifier?, Branching Logic, Required Field?, Custom Alignment, Question Number, Matrix Group Name, Matrix Ranking?, Field Annotation. | REDCap data dictionary template | unverified (the first upload on the Data Dictionary page did not reach the project; to be repeated) | `test_dictionary_csv_columns` |
| A16 | A Data Import Tool CSV has one row per record, the record ID column first, raw codes, and dates as `YYYY-MM-DD`. | REDCap Data Import Tool template | unverified | `test_import_csv_matches_dictionary` |
| A17 | A wrong token gets an error, not data. The error comes back as XML (`<hash><error>You do not have permissions to use the API</error></hash>`) whatever format was asked for; the client reads the message out of it. | REDCap 15.6.0 | verified | `test_bad_token_is_refused` |
| A18 | In a Development project, the API imports a whole data dictionary (`content=metadata`, JSON rows with the 18 API keys) and answers with the number of fields. The import replaces the existing dictionary. | REDCap 15.6.0, checked by hand | verified | — (comes with the dictionary upload feature) |
| A19 | A value that does not match an integer or number field ("abc", or "3.5" for an integer) is rejected: "The value you provided could not be validated because it does not follow the expected format. Please try again." | REDCap 15.6.0 | verified | `test_wrong_format_is_rejected` |
| A20 | Dates in the future are saved; REDCap does not check them. The app's own "not in the future" check is the only gate. | REDCap 15.6.0 | verified | `test_future_date_is_saved` |

When the mock and this table disagree, fix one of them and record why in `docs/DECISIONS.md`.
