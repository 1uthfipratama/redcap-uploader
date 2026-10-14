# REDCap Uploader

A desktop app (Windows and macOS) that guides a researcher through uploading a spreadsheet to REDCap. It reads SITB TBC.03 SO and RO register exports, or any sheet with one header row, and turns them into REDCap records:
- identifiers are dropped or pseudonymised
- answers are mapped to REDCap codes
- every row is validated before anything is sent

It runs against a built-in mock REDCap until a real project is available.

Status: prototype, phase 1a done (core pipeline, no UI yet). See [docs/PROGRESS.md](docs/PROGRESS.md).

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

## Privacy

Real exports never go in this repo. The app needs a pseudonym key from `REDCAP_UPLOADER_PSEUDONYM_KEY` (hex) or a key file named in `REDCAP_UPLOADER_KEY_FILE`, kept outside the repo. There is no default key.
