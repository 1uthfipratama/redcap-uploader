import json
import re
from pathlib import Path

from core.messages import I18N_DIR, LANGUAGES, strings

REPO = Path(__file__).resolve().parent.parent
NIK_STATUSES = ("blank", "scientific", "precision_lost", "not_digits", "wrong_length", "all_zero")


def test_language_files_have_the_same_keys():
    keys = [set(strings(lang)) for lang in LANGUAGES]
    assert keys[0] == keys[1], keys[0] ^ keys[1]


def test_language_files_are_valid_json_without_empty_text():
    for lang in LANGUAGES:
        data = json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        assert all(isinstance(v, str) and v.strip() for v in data.values())


def _issue_codes_in_core() -> set[str]:
    codes = set()
    for path in (REPO / "core").glob("*.py"):
        codes |= set(re.findall(r'Issue\(\s*"([a-z_]+)"', path.read_text(encoding="utf-8")))
    codes |= {f"nik_{s}" for s in NIK_STATUSES}
    return codes


def test_every_issue_code_has_a_message_and_a_fix_in_both_languages():
    for lang in LANGUAGES:
        s = strings(lang)
        for code in _issue_codes_in_core():
            assert f"issue.{code}" in s, (lang, code)
            assert f"fix.{code}" in s, (lang, code)


def test_placeholders_match_between_languages():
    en, id_ = strings("en"), strings("id")
    for key in en:
        assert set(re.findall(r"{(\w+)}", en[key])) == set(re.findall(r"{(\w+)}", id_[key])), key
