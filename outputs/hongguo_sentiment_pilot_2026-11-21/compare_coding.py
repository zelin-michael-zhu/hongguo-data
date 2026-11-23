"""Compare two text-only pilot readings without using future outcomes, accounts or ratings."""
import csv
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = ("series_id", "scope", "position")


def load(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {tuple(row[k] for k in KEYS): row["label"] for row in csv.DictReader(f)}


def main():
    first = load(HERE / "example_labels_first.csv")
    second = load(HERE / "example_labels_second.csv")
    assert first.keys() == second.keys() and len(first) == 48
    source = defaultdict(list)
    for key in first:
        source[key[:2]].append(key)
    rows = []
    for (sid, scope), keys in sorted(source.items()):
        counts_a = Counter(first[key] for key in keys)
        counts_b = Counter(second[key] for key in keys)
        record = {"series_id": sid, "scope": scope, "n_text": len(keys),
                  "same_label": sum(first[key] == second[key] for key in keys)}
        for name, counts in (("first", counts_a), ("second", counts_b)):
            for label in ("pos", "neg", "mixed", "other"):
                record[f"{name}_{label}"] = counts[label]
        rows.append(record)
    with (HERE / "example_coding_comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
