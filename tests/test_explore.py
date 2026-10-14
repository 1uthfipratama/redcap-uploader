"""Explore numbers checked against values worked out by hand on a tiny table."""

import datetime as dt
import time

import pandas as pd
import pytest

from core import explore
from core.parse import ROW
from tests.conftest import TEST_KEY, TODAY

D = dt.date


@pytest.fixture
def frame():
    # Five records of the SO profile's fields, already cleaned (codes, real dates).
    return pd.DataFrame({
        ROW: [18, 19, 20, 21, 22],
        "record_id": ["r1", "r2", "r3", "r4", "r5"],
        "patient_pid": ["p1", "p2", "p3", "p4", "p5"],
        "sitb_pid": ["s1", "s2", "s3", "s4", "s5"],
        "age": [20, 30, 40, None, 50],
        "sex": ["1", "2", "1", "1", None],
        "dm": ["0", "99", "1", None, "99"],
        "tx_start_date": [D(2024, 1, 5), D(2024, 1, 20), D(2024, 3, 2), D(2024, 3, 9), None],
    }, dtype=object)


@pytest.fixture
def fields(frame, so):
    return {f.name: f for f in explore.explorable_fields(frame, so)}


def test_identifiers_and_pseudonyms_are_never_offered(frame, so):
    names = {f.name for f in explore.explorable_fields(frame, so)}
    assert names == {"age", "sex", "dm", "tx_start_date"}
    assert not names & {"record_id", "patient_pid", "sitb_pid", ROW}


def test_field_kinds_and_unknown_codes(fields):
    assert fields["age"].kind == "numeric"
    assert fields["sex"].kind == "categorical"
    assert fields["tx_start_date"].kind == "date"
    assert fields["dm"].unknown_codes == {"99"}


def test_variable_summary_matches_hand_computed_values(frame, fields):
    table = explore.variable_summary(frame, list(fields.values()), "en").set_index("field")
    age = table.loc["age"]
    # ages 20, 30, 40, 50: mean 35, sample SD sqrt(500/3) = 12.9, median 35, quartiles 27.5 and 42.5
    assert (age["count"], age["blank"], age["blank_pct"]) == (4, 1, 20.0)
    assert (age["mean"], age["sd"], age["median"], age["min"], age["max"]) == (35.0, 12.9, 35.0, 20.0, 50.0)
    assert (age["q1"], age["q3"]) == (27.5, 42.5)
    dm = table.loc["dm"]
    assert (dm["count"], dm["blank"], dm["unknown"], dm["distinct"]) == (4, 1, 2, 2)
    assert table.loc["sex", "top"] == "Male (3); Female (1)"
    assert (table.loc["tx_start_date", "min"], table.loc["tx_start_date", "max"]) == ("2024-01-05", "2024-03-09")


def test_unknown_is_counted_apart_from_blank(frame, fields):
    miss = explore.missingness(frame, list(fields.values())).set_index("field")
    assert (miss.loc["dm", "blank"], miss.loc["dm", "unknown"], miss.loc["dm", "filled"]) == (1, 2, 2)
    assert (miss.loc["dm", "blank_pct"], miss.loc["dm", "unknown_pct"]) == (20.0, 40.0)
    counts = explore.distribution(frame, fields["dm"], "id")
    assert list(counts["label"]) == ["Ya", "Tidak", "Tidak diketahui", ""]
    assert list(counts["n"]) == [1, 1, 2, 1]
    assert list(counts["unknown"]) == [False, False, True, False]


def test_categories_follow_the_form_order_and_flag_small_groups(frame, fields):
    counts = explore.distribution(frame, fields["sex"], "en")
    assert list(counts["label"]) == ["Male", "Female", ""]
    assert list(counts["n"]) == [3, 1, 1]
    assert list(counts["percent"]) == [60.0, 20.0, 20.0]
    assert all(counts["small"])  # every group is under 5


def test_numeric_histogram_counts_every_value(frame, fields):
    bins = explore.distribution(frame, fields["age"], "en")
    assert bins["n"].sum() == 4
    # ages 20-50 in about 20 bins -> round width 2, from 20 up to 52 so that 50 has a bin
    assert bins["bin_start"].iloc[0] == 20.0 and bins["bin_end"].iloc[-1] == 52.0
    assert set((bins["bin_end"] - bins["bin_start"]).round(6)) == {2.0}


def test_bins_sit_on_round_numbers():
    edges = explore.nice_edges(0, 85, 20)
    assert edges[0] == 0 and edges[-1] == 90 and set(edges[1:] - edges[:-1]) == {5.0}
    assert list(explore.nice_edges(7, 7, 20)) == [6.5, 7.5]


def test_group_comparison_numeric(frame, fields):
    table = explore.group_comparison(frame, fields["age"], fields["sex"], "en").set_index("group")
    # Male: 20, 40 (age blank on the fourth record); Female: 30
    assert (table.loc["Male", "n"], table.loc["Male", "mean"], table.loc["Male", "median"]) == (3, 30.0, 30.0)
    assert table.loc["Female", "mean"] == 30.0 and pd.isna(table.loc["Female", "sd"])  # one value: no SD
    assert table["small"].all()


def test_answers_by_group(frame, fields):
    table = explore.answers_by_group(frame, fields["dm"], fields["sex"], "en")
    male = table[table["group"] == "Male"].set_index("answer")
    # Male rows: dm 0, 1 and blank -> answered 2: No 50%, Yes 50%, blank counted but no percent
    assert (male.loc["No", "n"], male.loc["No", "percent"]) == (1, 50.0)
    assert (male.loc["Yes", "n"], male.loc["Yes", "percent"]) == (1, 50.0)
    blank = table[(table["group"] == "Male") & table["blank"]]
    assert blank["n"].tolist() == [1] and blank["percent"].isna().all()
    female = table[table["group"] == "Female"].set_index("answer")
    assert (female.loc["Unknown", "percent"], bool(female.loc["Unknown", "context"])) == (100.0, True)
    assert list(dict.fromkeys(table["answer"])) == ["Yes", "No", "Unknown", ""]  # the form's order, blank last
    assert table["small_group"].all()


def test_records_without_a_group_are_counted(frame, fields):
    assert explore.ungrouped_count(frame, fields["sex"]) == 1


def test_distribution_gives_share_of_answered(frame, fields):
    counts = explore.distribution(frame, fields["sex"], "en").set_index("label")
    assert counts.loc["Male", "percent_answered"] == 75.0  # 3 of 4 answered
    assert pd.isna(counts.loc["", "percent_answered"])


def test_records_per_month_include_empty_months(frame, fields):
    months = explore.over_time(frame, fields["tx_start_date"])
    assert list(months["month"]) == ["2024-01", "2024-02", "2024-03"]
    assert list(months["n"]) == [2, 0, 2]


def test_overview(frame, fields):
    o = explore.overview(frame, list(fields.values()))
    assert (o["rows"], o["explorable"], o["duplicate_rows"]) == (5, 4, 0)
    assert (o["numeric"], o["categorical"], o["dates"]) == (1, 2, 1)


def test_generic_columns_are_inferred(profiles):
    frame = pd.DataFrame({ROW: [2, 3], "record_id": ["a", "b"], "age": ["34", "51"], "group": ["x", "y"]}, dtype=object)
    kinds = {f.name: f.kind for f in explore.explorable_fields(frame, profiles["generic"])}
    assert kinds == {"age": "numeric", "group": "categorical"}


def test_row_cap_uses_a_seeded_sample(frame):
    settings = {**explore.load_settings(), "row_cap": 3}
    a, sampled = explore.maybe_sample(frame, settings)
    b, _ = explore.maybe_sample(frame, settings)
    assert sampled and len(a) == 3 and a.index.tolist() == b.index.tolist()
    assert explore.maybe_sample(frame)[1] is False


def test_ten_thousand_rows_summarise_quickly(tmp_path, so):
    from core.pipeline import prepare
    from synthetic.generate import write_set

    files = write_set(so, tmp_path, 10_000, seed=3, formats=("xlsx",), today=TODAY)
    prepared = prepare(files["clean_xlsx"], so, TEST_KEY, today=TODAY)
    start = time.perf_counter()
    fields = explore.explorable_fields(prepared.frame, so)
    summary = explore.variable_summary(prepared.frame, fields, "en")
    explore.distribution(prepared.frame, next(f for f in fields if f.name == "age"), "en")
    elapsed = time.perf_counter() - start
    assert len(summary) == len(fields) > 50
    assert elapsed < 3.0, elapsed
