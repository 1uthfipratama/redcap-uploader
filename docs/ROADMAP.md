# Roadmap: from a TBC.03 uploader to a universal one

Today the app fully understands two forms (SITB TBC.03 SO and RO) and uploads them into a REDCap project whose fields it designed itself. "Universal" means four things it cannot do yet:

1. **Any SITB form**, not only TBC.03. That includes later SITB editions and exports at facility, district or province level.
2. **Any spreadsheet**, not only SITB: other registers, lab or hospital exports, and study case report forms. Values must be checked as strictly as TBC.03 values are.
3. **Any REDCap project**, including one the team already has, with its own field names, codes and design (events, repeating forms, checkboxes, data access groups).
4. **Any team, without a developer.** A data manager can add a new form, check it, and share it with other sites.

The plan below gets there in seven stages. Each stage ends in something that can be tested. The estimates are rough, for one developer.

## How it works today, and what has to change

Today a profile does two jobs at once: it describes the **source** (where each column is and how answers are spelled), and it fixes the **target** (REDCap field names and codes). That is why every form needs a REDCap project built from the app's own dictionary.

The main change is to split these:

| Today | Universal |
| --- | --- |
| Profile = source layout **and** REDCap fields and codes | **Source profile**: how to read a form, into standard variables and standard answer codes |
| | **Project mapping**: how those standard variables become one REDCap project's fields and codes, matched against that project's data dictionary, confirmed by the user, saved per project |
| Generic mode guesses fields by name and checks almost nothing | Generic mode checks every value against the target project's data dictionary: answers, numbers, ranges, dates, required fields |
| New form = a developer writes YAML | New form = a **profile builder** in the app, from one sample file |

## Stage 0: make TBC.03 production-solid (1–2 weeks, partly waiting)

Everything after this builds on a path that is proven with real data and a real server.

- **Real REDCap check (phase 7).** Run the contract tests against a test project, and mark all 17 assumptions verified or different.
- **Partial uploads.** Rows with errors can be set aside, listed in a report and never dropped silently, while the clean rows upload.
- **Learn spellings from use.** In the Check step, an "add this spelling to the profile" action (reviewed, versioned) closes the gaps the real-file dry run found.
- **Answer the open questions** in PROGRESS.md: TKM, "RD", required-when rules, free text, district, and one REDCap project or two.

*Done when:* the four real exports upload to a REDCap test project with every row either uploaded or set aside with a reason.

## Stage 1: split source profiles from project mappings (about 1 week)

- **Profiles describe the source only.** Each profile maps its columns to standard variables (age, sex, tb_site and so on) with standard codes. A shared vocabulary file holds the common answer sets (yes/no/unknown, microscopy, outcomes, HIV status) so forms reuse them.
- **A project mapping matches the standard variables to a project's data dictionary.**
  - It works by name, label and answer labels, with a confidence score.
  - The user confirms every match.
  - It is saved per REDCap project, so the next upload reuses it.
- **Two modes at Connect:**
  - **New project:** generate the dictionary, as today.
  - **Existing project:** build or reuse a mapping.
- **Code conversion through the mapping.** Answers are converted from standard codes to the project's codes (for example the project uses 1/2 for sex where the profile uses 1/0). Missing or extra answers are flagged.

*Done when:* the TBC.03 SO file uploads into a hand-made REDCap project with different field names and codes, using a saved mapping, with no code change.

## Stage 2: a Generic mode that is as strict as TBC.03 (about 1 week)

- **Read the target project's data dictionary at Connect** and check every value against it: choice codes (and choice *labels*, converted to codes), integers and numbers with their min and max, dates in any common format converted to the project's format, required fields and branching-required fields.
- **More layouts:**
  - several header rows without column numbers
  - a header that is not on the first row
  - choosing the sheet in a workbook
  - CSV with any delimiter or encoding (already done)
- **Identifier detection by content as well as name.** 16-digit numbers that look like NIKs, phone-number patterns and long free-text name-like columns are flagged and dropped unless the user decides otherwise.
- **Record ID choice:** use a column as is, pseudonymise it with the team key, or let REDCap number records.
- **"Save as profile":** a checked Generic mapping can be saved, so the same spreadsheet layout is recognised next time.

*Done when:* a non-SITB spreadsheet (for example a study's own case report form in Excel) goes through Check with the same kinds of errors and fixes as TBC.03, and uploads cleanly.

## Stage 3: a profile builder that needs no code (1.5–2 weeks)

- **A new "Create a profile" screen, using one sample file:**
  1. It detects the layout, then lists each column with its inferred type, fill rate and spellings. This is the inventory tool, in the app, local only.
  2. The user marks identifiers, picks standard variables or makes new ones, groups spellings into answers, and sets required fields and ranges.
  3. The draft profile is tested immediately on the sample file (a dry run) and on a synthetic file generated from it.
- **A profile library:**
  - Each profile carries a version, an edition and a fingerprint (column numbers and header labels), so the app recognises the right one.
  - The app explains the difference when a file matches no profile (for example "a new SITB edition: 3 columns added").
- **Sharing:**
  - Export and import a profile file.
  - A team can publish its profiles, for example in a GitHub release of a "profiles" repository, so other sites receive updates without reinstalling the app.

*Done when:* a data manager who has never seen YAML creates a working profile for a new form in under a day.

## Stage 4: more SITB forms and more sites (about 1–2 days per form)

For each form the team needs (other SITB registers such as TB.01 or TB.06, whichever are used):
1. Get one real export on the approved machine, then run the inventory tool, which reads structure only.
2. Build the profile with the profile builder.
3. Generate synthetic clean and messy files, and run the tests.
4. Dry-run the real export (counts only), then fix the profile until it passes.

Repeat the dry run with exports from **at least two other facilities** and **one district or province export**. That confirms nothing is tied to one site, and catches layout variants such as extra facility columns or a different title block.

*Done when:* every target form has a profile, and real exports from three sites pass the dry run with only true data problems left.

## Stage 5: any REDCap design (1–2 weeks)

Teach the client, the mock and the contract tests the REDCap features that real projects use:

| Feature | Why it matters | What changes |
| --- | --- | --- |
| Repeating instruments | RO follow-up months, repeated lab results | Wide columns become repeat instances; mapping supports them |
| Longitudinal events | Baseline, follow-up and outcome as visits | Records carry an event; mapping chooses events |
| Checkboxes (multi-select) | Side effects, symptoms, comorbidities | One answer list becomes several 0/1 fields |
| Data access groups | Multi-facility or district projects | Rows are assigned to a group by facility code |
| Auto-numbered record IDs | Projects where REDCap issues the ID | A pseudonymised secondary unique field is used to match updates |
| Projects in production status | Dictionary changes need approval | Missing fields are detected and the dictionary changes are prepared for the admin |

*Done when:* the contract tests pass against test projects that use each feature.

## Stage 6: running it every month, at scale (1–2 weeks)

- **Incremental uploads.** The monthly export only sends what changed. Records already in REDCap and unchanged are skipped, with counts.
- **Cross-file linking.** The same patient in SO and RO, or across facilities, is linked through `patient_pid` with the same team key. The app checks this and reports it.
- **Audit log** for every upload: when, who (initials), profile and version, file hash, counts and outcome. It never holds values.
- **Key management:** key backup and rotation guidance, and a check that the same key is used across uploads.
- **Signed installers** (Windows certificate, Apple notarisation) and an update check.
- **Large files:** streaming reads and batched checks for files of 100,000+ rows.

*Done when:* a team runs its monthly upload from a fresh export in under 15 minutes, with an audit trail.

## What is needed from the team

| Needed | For stage |
| --- | --- |
| A REDCap test project with API rights | 0, 1, 5 |
| The list of forms and sources the team wants to upload | 3, 4 |
| One real export per form, on the approved machine (only structure leaves it) | 4 |
| Exports from two other facilities and one district | 4 |
| One existing REDCap project the team did not design for this app | 1, 2 |
| Answers to the open questions in PROGRESS.md | 0 |
| A decision on who owns and publishes the shared profiles | 3 |

## How "universal" is measured

- A new form is added without code, by a data manager, in under a day.
- Real exports from three sites pass the dry run with no false errors.
- Any spreadsheet's values are checked against the target project before upload, as strictly as TBC.03.
- An existing REDCap project, with its own field names and codes, is filled through a saved mapping.
- Every test passes on Windows, macOS and Linux, including contract tests against real REDCap test projects.

## Making uploads easier (ideas, 2026-10-15)

Since this roadmap was written, the app gained "Add them to the project" (fields go into a Development project through the API), a guard against fields that share a name but differ in meaning, and "Create a data dictionary" from any spreadsheet. These are the next steps that would remove the most effort, roughly in order of value. Each is small enough to build and test on its own.

| # | Improvement | What it removes | Size |
| --- | --- | --- | --- |
| 1 | **Remember projects.** Saved connections (URL and project name), and the token kept in the computer's own password store (Windows Credential Manager, macOS Keychain) when the person agrees. | Copying and pasting the URL and token every time | 2 days |
| 2 | **Project readiness check at Connect.** A short checklist (Development or production, record ID field, auto-numbering, events, rights) with the exact place in REDCap to fix each item. | Failed uploads from project settings, and guessing why | 1–2 days |
| 3 | **Fix it once at the Check step.** For an unknown answer, pick what it means from the list; for an unreadable date, pick the format. The choice is saved in the form, so next month's file passes. | The same errors every month | 3 days |
| 4 | **Upload the clean rows.** Rows with errors are set aside and saved to a local "rows to fix" spreadsheet, with the reason on each row. | One bad row blocking a whole file | 2 days |
| 5 | **Match to an existing project.** Read the project's own dictionary, match columns to its fields, convert answer labels to its codes, and check formats against it. | Building the CSV by hand to fit someone else's instruments | 1 week |
| 6 | **See changes before overwriting.** "12 new, 3 changed, 185 unchanged", with the changed values listed, and an option to fill only empty fields so values entered by hand are never replaced. | Fear of overwriting manual corrections | 3 days |
| 7 | **Upload history and receipt.** Every upload logged (date, form, file fingerprint, counts, outcome, never values), with a one-page receipt to share with a supervisor or ethics committee. | "What did we upload, and when?" | 2 days |
| 8 | **Undo the last upload.** Delete the records it created and restore the values it changed, from a snapshot taken just before. | Mistakes that are hard to take back | 3 days |
| 9 | **An Excel template for a project.** A workbook with the right headers, dropdowns for answers and date cells, so data collected offline arrives clean. | Cleaning data after the fact | 2 days |
| 10 | **Several files at once.** Monthly exports from several facilities in one go, combined, with duplicates across files reported. | Repeating the wizard per file | 3 days |
| 11 | **Codebook export.** A readable document of a form's fields and answers, for protocols and ethics submissions. | Writing the codebook by hand | 1 day |
| 12 | **Scheduled uploads.** A command-line mode that runs a saved form against a folder, for monthly routines. | Manual monthly runs | 2 days |

Stage 5 (repeating instruments, events, checkboxes, data access groups) and Stage 6 (signed installers, updates) above still apply.

