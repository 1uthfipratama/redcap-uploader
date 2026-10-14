# REDCap Upload Prototype: PRD, Architecture and Feature List

2026-10-14 · @Luthfi

> Scope, 2026-10-14: the tool is for any researcher or programme team using SITB, not one study or site. The TBestie LTFU study is the first user.
>
> Snapshot of the PRD doc, 2026-10-14. Where it differs from `CONTRIBUTING.md` (record ID, upload path, mock framework), `CONTRIBUTING.md` wins.

## Overview

This is a standalone desktop app that lets a researcher pick a spreadsheet, click through a few steps and see it land in REDCap, with parsing, mapping and validation done for them. Once the data is cleaned, it also shows basic statistics and charts so the researcher can see what they have. It also works as a safe sandbox for learning what a REDCap upload involves, so it runs against a built-in mock server until a real REDCap account exists.

**Problem.** The TBestie LTFU study moves data from SITB exports (with EMR filling gaps) into REDCap, and no one on the team has a REDCap account or hands-on experience with its import flow yet. Manual entry is slow and error-prone, and a first upload to a live project is a bad time to learn what a rejected row looks like.

**Why a prototype first.** [PyCap](https://github.com/redcap-tools/PyCap) needs only an API URL and a token, so the app can be built and tested against a local mock now. Going live later means changing those two values, not the code.

**Product shape.** A native desktop app for Windows and macOS, installed with no Python or dependencies for the user to set up, in Bahasa Indonesia and English. It is form-agnostic: each source form (TBC.03 SO, TBC.03 RO, later others) is described by a form profile instead of being hard-coded. It ships in two stages: a prototype on synthetic data against a mock REDCap, then a production SITB-to-REDCap uploader once ethics approval, data-governance sign-off and REDCap access are in place. Visualization is descriptive: summaries and charts of the cleaned data, not statistical testing or modelling.

## Goals, non-goals and success metrics

The prototype succeeds if a first-time user completes a clean upload in under 5 minutes and the messy file is stopped by validation with messages they understand.

**Goals**

- Let a non-programmer upload a CSV, XLSX or XLS file to REDCap in a guided, click-only flow.
- Stay form-agnostic: TBC.03 SO and TBC.03 RO ship as form profiles, and a new form is a new profile, not new code.
- Teach what happens at each step: parsing, mapping, validation, the API call, the result.
- Let researchers explore the cleaned data with basic descriptive statistics and charts, without writing code.
- Run on both Windows and macOS, in Bahasa Indonesia and English.
- Prove the core pipeline (parse, map, validate, upload) as the prototype, then grow it into the real SITB-to-REDCap uploader.
- Switch from the mock to real REDCap by changing a URL and token only.

**Non-goals**

- Real patient data in the prototype stage, or any identifiable data in the repo. Real SITB extracts are used only in the production stage, on approved machines.
- Logins, multi-user support, cloud deployment, or a web version.
- Repeating instruments and longitudinal events (the RO follow-up months are imported as plain fields first), or file-upload fields.
- Merging SITB with EMR data, or any modelling (that belongs to the LTFU project).
- Inferential statistics (p-values, regression) or a custom report builder; the Explore screen is descriptive only.
- Pixel-perfect REDCap behaviour; the mock covers only the calls the app makes.

**Success metrics**

| Metric | Target |
| --- | --- |
| Time for a first-time user to finish a clean upload against the mock | Under 5 minutes, unaided |
| Messy synthetic file | Fails validation with row-level, plain-language messages |
| Clean synthetic file | Uploads with zero rejected rows |
| Switching mock to real REDCap | No code change, only URL and token |
| Core module test coverage | Tests for mapping and validation logic pass |
| Fresh Windows machine | Installs and launches with no extra software |
| Explore screen speed | Summary table and first chart in under 3 seconds on a 10,000-row file |
| Exporting results | Any chart saves as PNG and any summary table as CSV in two clicks |
| Both shipped forms (TBC.03 SO and RO) | A synthetic file with each form's real layout parses, validates and uploads end to end |
| Adding a new form | A new profile file only; no code change |
| Fresh Mac (Apple silicon) | Installs and launches with no extra software, after the documented first-run approval |
| Language | Every screen and message available in Bahasa Indonesia and English |

## Users and use cases

The primary user is a clinical researcher or research assistant who knows their spreadsheet but not REDCap's import rules. The secondary user is the developer (you), who uses the same app to test the pipeline before real access arrives.

| User | Needs | Typical task |
| --- | --- | --- |
| Researcher or research assistant | Simple clicks, clear errors, confidence nothing breaks | Upload a cleaned SITB export and see what was accepted or rejected |
| New team member or student | Understand what REDCap upload is | Walk through the wizard in demo mode with the teaching panels open |
| Developer | A reusable pipeline and a safe test target | Run the messy file, check validation, later point at a real test project |
| Study data manager | Add or adjust a form without a developer | Copy a form profile, edit its value maps, test it on a synthetic file |

**Key use cases**

1. Upload a clean file in demo mode and see every record accepted.
2. Upload a messy file, read the row-level errors, fix the source spreadsheet and retry.
3. Open a TBC.03 SO or RO export, let the app read its title block and merged header, and see every column matched to its REDCap field.
4. Map columns that do not match REDCap field names (for example `umur` to `age`) in Generic mode.
5. Add a new form by copying or building a profile.
6. Read the "What's happening?" panel to learn what API call was made.
7. Open the Explore screen after cleaning, spot a skewed or missing-heavy field, and save the chart for a report.
8. Switch the interface between Bahasa Indonesia and English.
9. Connect to a real REDCap project with a URL and token, then repeat the same flow.

## Product requirements

The app is a six-step wizard with a teaching layer and an optional Explore screen, running in Demo mode (built-in mock) or Real mode (URL and token). Demo mode is the default on first launch.

Every form-specific rule (header layout, column keys, value spellings, identifier handling, REDCap field names) comes from a form profile chosen in step 2, so the same wizard handles TBC.03 SO, TBC.03 RO and later forms.

**The wizard**

| Step | What the user does | What the app does | Done when |
| --- | --- | --- | --- |
| 1. Connect | Chooses Demo or Real; in Real enters URL and token | Calls project info through PyCap, shows project name | Project name is displayed |
| 2. Choose file and form | Picks a CSV, XLSX or XLS file (dialog or drag-and-drop) | Recognises the form from its title block and proposes a profile, or falls back to Generic; reads the merged multi-row header; skips title and summary rows; detects encoding and delimiter for CSV | Form, row and column counts shown |
| 3. Preview and map | Checks the first rows, fixes column matches | Matches columns by the profile's official column numbers (or by name and similarity in Generic mode); marks identifier columns to drop or pseudonymise; lists unmatched columns | Every column is mapped, ignored, dropped or flagged |
| 4. Validate (dry run) | Clicks Validate | Applies the profile's value maps, then checks required fields, allowed choices, number ranges, date formats and duplicate IDs; lists every spelling it changed; sends nothing | Errors listed per row and column, or a clean pass |
| 5. Upload | Clicks Upload | Calls `import_records` in batches with progress | All batches finished or stopped on error |
| 6. Result | Reviews the outcome | Shows imported and rejected counts with reasons; offers a log download | Log saved to a chosen folder |

**Explore screen (basic statistics and charts)**

An optional screen that opens from step 4 once the data passes validation, and again from the Result step. It describes the cleaned, mapped data in memory. It does not test hypotheses or fit models, and it sends nothing to REDCap.

| Panel | What the researcher sees |
| --- | --- |
| Data overview | Rows and columns, duplicate count, mapped and ignored columns, records per category |
| Variable summary | One row per field: type, count, missing count and percent, unique values; numeric fields add mean, median, SD, min, max and quartiles; categorical fields add the most common values |
| Distributions | Histogram for a numeric field, bar chart for a categorical field, picked from a field list |
| Missingness | Missing percent per field, with "Tidak diketahui" counted separately from blank |
| Group comparison | Pick a category such as `sex`, `tb_site` or `hiv` and compare another field across its groups |
| Over time | Records per month by treatment start date, when a date field is mapped |

- Fields are chosen from lists; no code or formulas.
- Every chart has Save as PNG and every summary table has Save as CSV.
- Groups with fewer than 5 records are flagged, as a reminder to check disclosure rules before sharing.
- Each panel has a plain-language "What's happening?" note, for example what a median is and why missing data matters.
- A visible note says these are summaries of this file, not analysis results.
- The summary table and first chart render in under 3 seconds for 10,000 rows.

**Teaching layer**

- Each step has a collapsible "What's happening?" panel in plain language.
- The panel shows the real API call (content type, parameters) with the token masked.
- Error messages say what is wrong, where, and how to fix it, for example "Row 14, age: 212 is above the allowed maximum of 120."

**Demo and Real modes**

- Demo mode starts an embedded mock REDCap on a random local port. The app talks to it over real HTTP, so the API calls shown are the ones real REDCap would receive.
- Real mode uses the same code path with a different URL and token.
- The mock serves project info, the data dictionary, record import and record export, and returns realistic errors for bad values.
- The mock's data dictionary follows the LTFU study variables (`age`, `sex`, `tb_site`, `hiv`, `dm`, `cxr` and so on), and "Tidak diketahui" stays its own category, never recoded as "no".

**Synthetic data**

- A generator produces fake exports that reproduce the real TBC.03 SO and RO layouts (title block, merged multi-row header, column numbers, text dates, a summary row): one clean file and one deliberately messy file (spelling variants, missing IDs, out-of-range age, duplicate IDs).
- The generator never reads a real file and never produces realistic names, NIK or addresses.
- The mock's data dictionary can be exported as a REDCap-importable CSV to help set up the real project.

## Form profiles: one app, many forms

Everything specific to a source form lives in a profile file, so the same app reads TBC.03 SO, TBC.03 RO and later forms without code changes. The two sample exports show why: they share a layout but differ in size and content.

**What the two samples look like** (structure only; no patient values were copied into this doc)

| Property | TBC.03 SO (drug-sensitive) | TBC.03 RO (drug-resistant) |
| --- | --- | --- |
| Edition and period in the sample | Edition 3 (2020); January 2020 to December 2024 | Edition 3 (2020); January to December 2025 |
| Data rows | About 3,650 | About 200 |
| Official columns | 84, numbered (1) to (84) | 114 numbers, (1) to (114); some cover a smear and culture pair, so the sheet has 144 columns |
| Layout | Title block (form name, facility, period), then a header spread over several rows with merged cells | Same style |
| Shared | Registration numbers, demographics, patient address, contact tracing, anatomical site, prior-treatment class, DM, HIV, regimen, final outcome | Same groups |
| Only in this form | Treatment-standard status, child TB score, tuberculin or IGRA, drug source, smear at months 2, 3, 5 and end, TB-HIV and TB-DM follow-up, a flag for patients moved to RO | Satellite facility, prior-treatment detail, drug-by-drug Xpert XDR results, standard susceptibility panel, paired smear and culture for follow-up months 1 to 24, the outcome "Gagal karena Perubahan" |

**What the app has to handle**

| What the files do | How a profile handles it |
| --- | --- |
| A title block sits above the header | Read as metadata (facility, period) for the import log, then skipped as data |
| The header is split over several rows with merged cells | Flattened to "group > subgroup > column"; the official column number, such as (39), is the stable key because labels change between editions |
| Dates are stored as text (dd/mm/yyyy) | The profile gives the date format; unreadable dates are reported with row and column |
| One answer is spelled several ways ("Tidak Diketahui" and "Tidak Tahu"; "Neg" and "NEG"; "TDL" for not done) | A value map per field; spellings not in the map are listed for the user, never guessed; "Tidak diketahui" stays its own category |
| Value sets differ between forms (the RO outcome list has an extra category; the RO DM field has no "unknown") | Each form profile carries its own choices |
| Some columns are empty in an export, or identical on every row (the facility address block) | The profile marks them ignore or constant |
| Some columns are blank by design (pregnancy status, child TB score, HIV therapy) | Required only when a stated condition holds; otherwise blank is not an error |
| A summary row follows the last numbered row | Detected and skipped, with a message |
| Patient identifiers are present: national ID (NIK), name, full address, BPJS number, medical record number, registration numbers | Each column has a role: drop, pseudonymise with a keyed hash that stays the same across episodes, or keep. The default is drop or pseudonymise; raw identifiers never reach logs, charts or the REDCap client |
| Follow-up months 1 to 24 repeat as wide blocks, each with smear and culture | Imported as ordinary fields first (for example `bta_m1` to `bta_m24`); repeating instruments are a later option |
| A column flags SO patients moved to RO | Kept as a field; matching the same patient across the two forms is a later feature |

**What a profile contains**

| Part | What it says |
| --- | --- |
| Identity | Form name, edition, and the title text used to recognise it |
| Layout | Header rows, the row holding column numbers, first data row, summary-row rule |
| Columns | Official number, label, stable key, type |
| Roles | Record ID, identifier (drop or pseudonymise), data, ignore |
| Value maps | Spelling variants mapped to one coded value, with unknown values reported |
| Rules | Required, ranges, date format, required-when conditions |
| REDCap mapping | Field name, choices, instrument |
| Labels | Indonesian and English text for each field and message |

Profiles are readable YAML files, one per form and edition. Two ship with the app (TBC.03 SO and TBC.03 RO), plus a Generic profile that handles any single-header spreadsheet by name matching. A new form is added by copying a profile or, as a Should-have, with a profile builder that reads a sample file. If a file's layout does not match its profile (for example a newer SITB edition), the app says so before reading it.

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Installation | Windows installer (Inno Setup) and macOS disk image (.dmg), each wrapping a PyInstaller one-folder build; no Python or libraries needed on the user's machine |
| Platform | Windows 10/11 and macOS (Apple silicon first); both are in scope |
| Size | Roughly 100-250 MB with Qt and matplotlib (approximate), accepted |
| Startup | Window visible in under 5 seconds on a typical laptop |
| Privacy | Prototype: synthetic data only. Production: real data only on approved machines, processed locally, identifiers dropped or pseudonymised before any upload. No data leaves the machine in Demo mode; no telemetry |
| Token handling | Held in memory only; optional OS keyring for "remember me"; never written to a plain file or the log |
| Log content | No cell values from real data in logs by default; row numbers, field names and error types only |
| Reliability | A failed batch never leaves the user unsure what was imported; the result screen reports per-batch status |
| Network | Real mode works only where the REDCap server is reachable (hospital network or VPN may be needed) |
| Usability | Every step reachable with the mouse; plain-language labels; error text never shows a raw stack trace |
| Language | Bahasa Indonesia and English from the first release, switchable in the app; text kept in one strings file per language |
| Maintainability | UI-independent core module with tests; all settings in config, not code |
| Windows warnings | Unsigned exe may trigger SmartScreen or antivirus false positives; documented workaround, code-signing certificate as a later option |
| Explore performance | Summary table and first chart in under 3 seconds for 10,000 rows; larger files are sampled or aggregated with a visible message |
| Explore privacy | Computed in memory only; exported charts and tables carry no identifiers; groups under 5 records are flagged |
| Input formats | CSV, XLSX and legacy XLS (the SITB exports shared so far are .xls) |
| macOS warnings | An unsigned app is blocked by Gatekeeper until the user approves it in System Settings (Privacy & Security); signing and notarisation need a paid Apple Developer account, to decide before wider rollout |
| Audit trail (production) | Every upload writes a log: when, form profile and version, file hash, record counts, outcome; never cell values |

## Architecture

The app is a thin Qt wizard over a UI-independent core pipeline, and only the REDCap client touches the network.

architecture · 6 components, 2 REDCap targets

The wizard calls the core pipeline, which calls one REDCap client. Demo mode points that client at the embedded mock, Real mode at your REDCap server. The Explore module takes clean data from the core and hands summaries and charts back to the UI. The highlighted core is the reusable part. Form profiles tell it how to read each source form.

**Tech stack**

| Layer | Choice | Why |
| --- | --- | --- |
| UI | PySide6 (Qt) | Native window, packages cleanly, no browser needed |
| Core | Plain Python 3.10+ module | Testable without the UI; reusable for the SITB-to-REDCap script |
| File parsing | pandas, openpyxl, xlrd (legacy .xls) | CSV, XLSX and XLS with encoding and delimiter detection |
| REDCap client | PyCap | Wraps the REDCap API; only the core's client wrapper imports it |
| Mock server | FastAPI or Flask in a background thread | Real HTTP, so PyCap behaves as it would against REDCap |
| Validation | Rules built from the project's data dictionary | Required, type, choices, min/max; adapts to any project |
| Secrets | Environment variables, optional OS keyring | Token never in a plain file or the log |
| Tests | pytest | Mapping, validation and a contract test for the mock |
| Packaging | PyInstaller one-folder; Inno Setup (Windows) and .dmg (macOS) | Installs on each OS with nothing else |
| Statistics | pandas, in core/explore | Summaries, group-by and missingness without UI code; descriptive only and unit-tested |
| Charts | matplotlib with the Qt backend | Familiar histogram, bar and line charts that save to PNG; adds some build size, so import it lazily |
| Form profiles | YAML files read with pydantic | Readable, versionable, and editable by a data manager without code |
| Languages | One strings file per language (Indonesian, English) | Whole UI and messages switchable at runtime |
| Build and release | GitHub Actions on Windows and macOS runners | PyInstaller cannot cross-compile, so each OS is built on its own OS |

**Repo layout**

```
redcap-uploader/
  app/           PySide6 wizard, step screens, Explore screen, teaching panels
  core/          profile, layout, parse, map, normalise, validate, upload, explore (no UI imports)
  profiles/      form profiles: tbc03_so.yaml, tbc03_ro.yaml, generic.yaml
  mock_redcap/   embedded mock server and data dictionary
  synthetic/     generators that reproduce the TBC.03 layouts with fake values
  i18n/          id.json, en.json
  config/        settings
  tests/
  build/         PyInstaller specs; Inno Setup (Windows); dmg and signing scripts (macOS)
  .github/       CI that builds on Windows and macOS runners
```

**Design decisions**

- The UI never imports PyCap, so switching modes needs no UI change.
- Mode is a single setting, base URL plus token; the rest of the code is identical.
- Everything form-specific lives in profiles; the core has no TBC.03 constants.
- Identifiers are handled right after parsing: dropped or pseudonymised per the profile, so raw values never reach logs, charts or the REDCap client.
- The mock binds to 127.0.0.1 on a random free port, so nothing is exposed to the network.
- Validation uses the data dictionary fetched at connect time, so it follows the project, not hard-coded rules.
- All statistics are computed in `core/explore` and the UI only draws them, so the same functions run in tests and could later feed a report.
- The "What's happening?" panels read from a log of the requests the client actually made, with the token masked, rather than hand-written examples.
- One code base builds for Windows and macOS through CI; nothing in `core/` is OS-specific.

## Candidate features

Nineteen features are must-haves for the prototype; the rest are options to pick from. Priorities assume Windows and macOS, both languages, and a path to the production uploader.

**Must have (the prototype)**

| Feature | What it does |
| --- | --- |
| Embedded mock REDCap | Local HTTP server answering project info, data dictionary, record import and export |
| Demo / Real toggle | Same code path; only URL and token differ |
| Form profiles | Profile loader with TBC.03 SO and RO shipped, plus a Generic profile for any single-header spreadsheet |
| Layout reader | Reads the title block, merged multi-row header and official column numbers; skips summary rows |
| File picker with drag-and-drop | Native dialog for CSV, XLSX and XLS |
| Robust parsing | Detects encoding and delimiter for CSV; handles blank rows and text dates |
| Column mapping | Matches by official column number (profile) or name similarity (Generic); user can correct |
| Identifier handling | Marks NIK, name, address, BPJS and record numbers; drop or pseudonymise by default; warns about look-alike columns in Generic mode |
| Value normalisation | Maps spelling variants to one value per profile, lists unknown spellings, keeps "Tidak diketahui" as its own category |
| Dry-run validation | Required fields, allowed choices, ranges, date formats, duplicate IDs; nothing sent |
| Batched upload | `import_records` in batches with a progress bar |
| Result screen and log | Imported and rejected counts with reasons; downloadable log |
| "What's happening?" panels | Plain-language explanation plus the real API call, token masked |
| Bahasa Indonesia and English | Whole UI and messages, switchable in the app |
| Synthetic data generator | Clean and messy files with the real TBC.03 SO and RO layouts and fake values |
| Windows and macOS installers | One-click install on each OS, built by CI |
| Core tests | Mapping, layout reader, normalisation, validation, and that the token never appears in logs |
| Explore: variable summary | Per-field type, count, missing, unique values and basic numeric statistics |
| Explore: charts | Histogram or bar chart for any field, with Save as PNG |

**Should have (high value, low cost)**

| Feature | What it does |
| --- | --- |
| Profile builder | Builds a profile from a sample file of a new form: detects header rows, assigns keys and roles, drafts value maps |
| Profile version check | Warns when a file's layout differs from its profile, for example a newer SITB edition |
| Value recoding suggestions | Proposes a fix for an unknown spelling, applied only after the user confirms |
| Saved mapping corrections | Reuse a user's column corrections across files of the same form |
| Fix-in-place | Edit an invalid cell in the preview instead of reopening the spreadsheet |
| Annotated error export | Download the original file with an error column per row |
| Data dictionary viewer | Browse fields, types and allowed values inside the app |
| Dictionary CSV export | Export the mock dictionary in REDCap import format to set up the real project |
| Missing-value report | Shows blanks per field and keeps "Tidak diketahui" as its own category |
| First-run tour and sample files | Button that loads the clean or messy example |
| Source flag support | Carries `<var>_source` (sitb or emr) columns through to REDCap |
| Explore: missingness chart | Missing percent per field, with "Tidak diketahui" shown apart from blank |
| Explore: group comparison | Compare a field across categories such as sex, tb\_site or hiv |
| Explore: records over time | Monthly counts by treatment start date |
| Summary and chart export | Variable summary as CSV, or the whole Explore screen as one HTML report |
| Small-count flag | Marks any group with fewer than 5 records |
| Cross-tab | Count table of two categorical fields |

**Could have**

| Feature | What it does |
| --- | --- |
| Overwrite options | Choose normal or overwrite behaviour on import |
| New vs update preview | Compare incoming records with existing ones before upload |
| Remember token | Store the token in the OS keyring, opt-in |
| Command-line mode | Run the same pipeline headless for scripted uploads |
| Import history | List of past uploads with their logs |
| Dark mode | Theme toggle |
| Intel Mac build | Add if any researcher uses an Intel Mac, or build a universal app |
| Update check | Notifies when a newer version exists |
| Chart builder | Choose x, y and chart type freely |
| Outlier highlighting | Marks values outside the allowed range or far outside the interquartile range |
| Correlation matrix | Heatmap of relationships between numeric fields |
| Interactive charts | Hover values, zoom, and copy a chart to the clipboard |

**Later or out of scope**

| Feature | Why not now |
| --- | --- |
| Automatic SITB folder watching and scheduled uploads | Needs real data flow and ops decisions first |
| EMR merge | Belongs to the data pipeline, not the uploader |
| Longitudinal events and repeating instruments | Not used by the baseline LTFU model; RO follow-up months are imported as plain fields first |
| File-upload fields | Not needed for tabular data |
| Windows certificate and Apple Developer account | Paid; unsigned apps show warnings on both systems, so decide before wider rollout |
| Multi-project and multi-user support | Adds accounts and permissions the prototype avoids |
| Statistical tests and regression | Inferential statistics need an analysis plan and belong to the study's statistical workflow |
| Risk scores and model views | LTFU prediction belongs to the modelling project, not this uploader |
| SO to RO patient matching | Needs one pseudonym key shared by both forms and a decision on how episodes link |
| Direct connection to SITB | Needs agreement with the SITB owners; exports are used for now |

## Milestones and effort

The must-have set is about 6-7 focused days, in this order. Each milestone ends with something that runs.

1. **Core, profiles and mock (1.5 days).** Data dictionary, mock server, profile loader, layout reader, parse for CSV, XLSX and XLS, map, normalise, validate and upload, with tests, run from a script. Gate: a small file with the TBC.03 layout uploads to the mock from the command line.
2. **Synthetic data (1 day).** Generators that reproduce the TBC.03 SO and RO layouts, clean and messy. Gate: the messy file fails validation with the expected errors.
3. **Desktop UI (1.5 days).** PySide6 wizard for the six steps in both languages, embedded mock on a random port, Demo/Real toggle. Gate: a non-coder completes the flow in under 5 minutes.
4. **Explore screen (1 day).** Summary, group-by and missingness functions with tests, then matplotlib charts in the Qt app with PNG and CSV export. Gate: every mapped field has a summary and a chart, and the 10,000-row file renders in under 3 seconds.
5. **Teaching layer (0.5 day).** "What's happening?" panels with masked API calls, plain-language errors and Explore notes. Gate: every step and Explore panel has a note.
6. **Packaging for Windows and macOS (1 day).** PyInstaller builds with an Inno Setup installer and a .dmg, produced by CI, with size and startup measured. Gate: installs and runs on a clean Windows machine and a clean Mac.
7. **Real REDCap check (after account arrives, about 1 hour).** Run the flow against a real test project and fix any difference in error formats or validation. Gate: same flow works with only URL and token changed.

**Stage 2: production uploader.** It starts after ethics approval, data-governance sign-off and a real REDCap project. It adds identifier checks on real exports, an audit log, profile versioning for new SITB editions, code signing and a first run on a small approved extract. A rough estimate is 3-4 further days, then the Should-have features as needed; the profile builder and value recoding suggestions are the best first picks.

## Risks, open questions and decisions needed

The biggest risk is that the mock behaves differently from real REDCap, so the first real test project may surface surprises.

**Risks**

| Risk | Mitigation |
| --- | --- |
| Mock differs from real REDCap (error formats, validation rules) | Budget an hour of testing against a real test project; keep the mock's surface small |
| Real REDCap not reachable from outside the hospital network | Confirm network and API access policy with the REDCap administrator early |
| API access needs approval or a token request | Ask the administrator for the steps, usual wait and any rate limits before the account arrives (see REDCap API access below) |
| Windows SmartScreen or antivirus flags the unsigned build | Use one-folder build in an installer; document "Run anyway"; consider code signing later |
| Real data used by mistake in the prototype | Identifier guard, synthetic-only defaults, and a banner in Demo mode |
| Real project dictionary does not match the mock | Design the mock dictionary to export as a REDCap-importable CSV |
| Packaged Qt app grows large or slow to start | Exclude unused Qt modules; measure startup in milestone 5 |
| Researchers read descriptive charts as study results | Keep the Explore screen descriptive only, with a visible note and no p-values; label exports as summaries of this file |
| Matplotlib enlarges the build and slows startup | Import charting lazily, exclude unused backends, and measure in the packaging milestone |
| Charts or tables are slow on large files | Sample or aggregate before plotting and show a message when it happens |
| Small counts in shared charts could identify patients | Flag groups under 5, remind users to check disclosure rules, and use synthetic data only in the prototype |
| SITB layout or column numbering changes between editions | Profiles are versioned; the app compares a file's layout to its profile before reading it; the profile builder helps adapt |
| Real SITB exports contain NIK, names and addresses | Identifier handling is a must-have; real files only on approved machines; raw identifiers never written to logs or charts; the prototype uses synthetic files with the same layout |
| Pseudonym key lost or changed, so one patient gets different study IDs | Keep the key in a protected place, version it, and log which key version produced each upload |
| macOS blocks the unsigned app | Document the first-run approval steps; budget an Apple Developer account before wider rollout |
| Two operating systems double the testing | CI builds both; run the same smoke test (demo flow with a clean and a messy file) on each OS for every release |

**REDCap API access: what an administrator's decision means**

An API token is a key tied to one user and one project that lets a program such as PyCap read or write records as that user. "Allowing API tokens" usually means two things: the user is given API rights in the project, and the REDCap administrator approves the token request. The points below come from policies published by other institutions, so check your own.

- **Cost.** The pages checked list no fee for API use. One institution notes charges only for custom support when setting up integrations. Hosting and licensing are the institution's matter, not charged per call.
- **Effect on others.** None. A token acts only as its owner, within that user's rights, on that one project.
- **Approval.** Usually a short use-case form. Some institutions start tokens in a test environment and issue a production token only after the code is reviewed.
- **Rights needed.** Import needs API import rights plus create and edit rights on each form; export needs API export rights plus export rights on each form.
- **Limits.** Avoid frequent full exports or high-frequency polling; a token that strains the server can be revoked. Some institutions expire unused tokens or ask for yearly re-confirmation.
- **Security.** A token is as powerful as the owner's login for that project. Keep it in an environment variable or the OS keyring, never in code, chat or email, and have it regenerated if exposed.

Questions to ask your administrator: what the steps and usual wait are; whether API use is allowed for patient data on this project; whether a test project is available first; whether there are rate limits; and which networks can reach the API (hospital network or VPN).

Sources: [OHSU REDCap API page](https://wiki.ohsu.edu/display/REDHelp/API), [Mount Sinai REDCap API Fair Use Policy](https://icahn.mssm.edu/files/ISMMS/Assets/Research/Research%20Portal/REDCap-API-Fair-Use-Policy.pdf).

**Open questions**

- Windows, Mac, or a mix? Both; the macOS build is in scope.
- Which SITB column names will appear? The TBC.03 SO and RO layouts from the two sample files; the app is form-agnostic through profiles.
- Teaching tool or real uploader? Both: prototype first, then the production uploader.
- Indonesian UI at launch or English first? Both languages from the first release.
- Which Should-have features before the first demo? Assumed: identifier handling and value normalisation are now must-haves; the profile builder waits for stage 2.
- First Explore fields and charts? Assumed: age, sex, tb\_site, hiv, dm, cxr and records over time, with defaults set per form profile.
- Ask the REDCap administrator the questions listed above before requesting a token.
- Is ethics approval and data-governance sign-off in place for running real SITB extracts through the app? It gates stage 2.
- Does any researcher use an Intel Mac? That decides whether a second Mac build is needed.
- Which forms come after TBC.03 SO and RO? Their sample files would become the next profiles.
- RO follow-up months: keep them as wide fields (default) or use REDCap repeating instruments later?
- Where will real exports live on approved machines, and who holds the pseudonym key?
