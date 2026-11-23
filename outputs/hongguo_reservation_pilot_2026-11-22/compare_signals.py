"""Compare same-snapshot reservation signals against observed first-week favorites."""

import argparse
import csv
import json
from collections import Counter
from itertools import combinations, groupby
from pathlib import Path
from statistics import correlation


SIGNALS = ("pre_reservations", "pre_expectation")
ENDPOINTS = ("day0_favorite", "day7_favorite")
CLASSIFICATIONS = ("first_work", "sequel", "unknown")


def tied_ranks(values):
    ranks = [0.0] * len(values)
    ordered = sorted(enumerate(values), key=lambda entry: entry[1])
    first = 1
    for _, entries in groupby(ordered, key=lambda entry: entry[1]):
        tied = list(entries)
        average = first + (len(tied) - 1) / 2
        for index, _ in tied:
            ranks[index] = average
        first += len(tied)
    return ranks


def spearman(predictor, outcome):
    if len(set(predictor)) < 2 or len(set(outcome)) < 2:
        return None
    return correlation(tied_ranks(predictor), tied_ranks(outcome))


def paired_ordering(rows, within_format=False):
    comparable = 0
    outcome_ties = 0
    credits = Counter()
    strict_disagreements = 0
    correct_on_disagreement = Counter()
    for left, right in combinations(rows, 2):
        if within_format and (not left["format"] or left["format"] != right["format"]):
            continue
        outcome_difference = left["week_gain"] - right["week_gain"]
        if outcome_difference == 0:
            outcome_ties += 1
            continue
        comparable += 1
        directions = [left[key] - right[key] for key in SIGNALS]
        for key, direction in zip(SIGNALS, directions):
            if direction == 0:
                credits[key] += 0.5
            elif direction * outcome_difference > 0:
                credits[key] += 1
        if directions[0] * directions[1] < 0:
            strict_disagreements += 1
            for key, direction in zip(SIGNALS, directions):
                if direction * outcome_difference > 0:
                    correct_on_disagreement[key] += 1

    return {
        "pairs_with_different_favorite_gains": comparable,
        "pairs_tied_on_favorite_gain": outcome_ties,
        "pairwise_concordance": {
            key: credits[key] / comparable if comparable else None for key in SIGNALS
        },
        "pairs_ranked_oppositely_by_signals": strict_disagreements,
        "correct_signal_on_oppositely_ranked_pairs": {
            key: correct_on_disagreement[key] for key in SIGNALS
        },
    }


def summarize(rows):
    gains = [row["week_gain"] for row in rows]
    correlations = {key: spearman([row[key] for row in rows], gains) for key in SIGNALS}
    difference = None
    if all(value is not None for value in correlations.values()):
        difference = correlations["pre_reservations"] - correlations["pre_expectation"]
    return {
        "n_complete": len(rows),
        "format_counts": dict(Counter(row["format"] for row in rows)),
        "spearman": correlations,
        "spearman_reservations_minus_expectation": difference,
        "ordering": paired_ordering(rows),
        "ordering_within_format": paired_ordering(rows, within_format=True),
    }


def compare(rows):
    groups = {group: [] for group in CLASSIFICATIONS}
    seen = set()
    incomplete = 0
    for row in rows:
        classification = row["classification"]
        if classification not in groups:
            raise ValueError(f"Unknown classification: {classification!r}")
        series_id = row["series_id"]
        if not series_id or series_id in seen:
            raise ValueError(f"Missing or duplicate series ID: {series_id!r}")
        seen.add(series_id)
        if any(not str(row.get(key) if row.get(key) is not None else "").strip()
               for key in (*SIGNALS, *ENDPOINTS)):
            incomplete += 1
            continue
        values = {key: int(row[key]) for key in (*SIGNALS, *ENDPOINTS)}
        if any(value < 0 for value in values.values()):
            raise ValueError(f"Negative input count for {series_id}")
        gain = values["day7_favorite"] - values["day0_favorite"]
        reported = row.get("week_gain")
        if reported not in (None, "") and int(reported) != gain:
            raise ValueError(f"Favorite gain does not agree with endpoints for {series_id}")
        groups[classification].append({**row, **values, "week_gain": gain})
    return {
        "n_input": len(seen),
        "n_incomplete": incomplete,
        "n_complete_unclassified": len(groups["unknown"]),
        "groups": {key: summarize(groups[key]) for key in ("first_work", "sequel")},
        "interpretation": (
            "Descriptive ranks on identical complete titles; null estimates are undefined. "
            "Outcome ties are excluded from concordance, and predictor ties count as half. "
            "Title pairs overlap, so pair counts are not independent sample sizes. "
            "Treat small groups as a pilot and use later release cohorts to validate differences."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        result = compare(csv.DictReader(handle))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        temp = args.output.with_suffix(args.output.suffix + ".tmp")
        temp.write_text(rendered, encoding="utf-8")
        temp.replace(args.output)
    print(rendered, end="")


if __name__ == "__main__":
    main()
