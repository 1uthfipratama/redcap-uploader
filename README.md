# REDCap Uploader

A desktop app (Windows and macOS) that guides any researcher or TB programme team using SITB through uploading a spreadsheet to REDCap. It reads SITB TBC.03 SO and RO register exports, or any sheet with one header row, and turns them into REDCap records:
- identifiers are dropped or pseudonymised
- answers are mapped to REDCap codes
- every row is validated before anything is sent

It runs against a built-in mock REDCap until a real project is available.

Status: prototype; phases 1a, 1b and 2 done (core pipeline, mock REDCap, client and upload, synthetic data; no UI yet). See [docs/PROGRESS.md](docs/PROGRESS.md).

## Develop

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

On macOS use `.venv/bin/python`.

## Where things are

- `CONTRIBUTING.md`: the rules for anyone changing this code. Read it first.
- `docs/PRD.md`: what is being built, and the milestones.
- `docs/PROGRESS.md`: where the build is now, and what comes next.
- `docs/DECISIONS.md`: the decisions made so far, and when to revisit them.
- `profiles/`: one YAML file per source form.
- `docs/forms/`: column inventories of the real exports (structure only, no patient data).

## Using it at your site

The tool is not tied to one facility or study:
- **Your own REDCap.** Each team uses its own REDCap project and settings.
- **Your own pseudonym key.** Each team keeps its own key. The same key must be used for every upload in a study, or patients will not link across files.
- **New spellings.** The TBC.03 profiles were built from one facility's exports. Spellings the profiles do not know yet are reported, not guessed, so profiles can be extended for other sites.

## Privacy

Real exports never go in this repo. The app needs a pseudonym key from `REDCAP_UPLOADER_PSEUDONYM_KEY` (hex) or a key file named in `REDCAP_UPLOADER_KEY_FILE`, kept outside the repo. There is no default key. To make one:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Store it where your team keeps secrets, and back it up: a lost key means new uploads can no longer be linked to earlier ones.
