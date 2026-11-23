"""Validate blind labels and summarize visible comment coverage."""
import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAGS = (
    "narrative_positive", "narrative_negative", "production_positive", "production_negative",
    "continue_intent", "stop_intent", "overall_positive", "promo",
)
DIMENSIONS = {
    "narrative": TAGS[0:2], "production": TAGS[2:4], "watch_intent": TAGS[4:6],
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validated(path, required_ids):
    groups = json.loads(path.read_text(encoding="utf-8"))
    if set(groups) != set(TAGS):
        raise ValueError(f"Incomplete label keys in {path.name}")
    for tag, ids in groups.items():
        if (not isinstance(ids, list) or any(type(value) is not int for value in ids)
                or len(ids) != len(set(ids)) or not set(ids) <= required_ids):
            raise ValueError(f"Invalid {tag} IDs in {path.name}")
    return {tag: set(ids) for tag, ids in groups.items()}


def summarize():
    rows = read(HERE / "11月21日_标注索引.csv")
    memberships = {tag: set() for tag in TAGS}
    for batch in "abc":
        expected = {int(row["row_id"]) for row in read(HERE / f"11月21日_盲标_{batch}.csv")}
        for tag, ids in validated(HERE / f"labels_{batch}.json", expected).items():
            memberships[tag].update(ids)
    tags = {tag: ids for tag, ids in memberships.items()}
    tags.update({key: memberships[first] | memberships[second] for key, (first, second) in DIMENSIONS.items()})
    audience = {int(row["row_id"]) for row in rows} - memberships["promo"]
    summary = []
    for tag, ids in tags.items():
        picked = [row for row in rows if int(row["row_id"]) in (ids if tag == "promo" else ids & audience)]
        by_scope = Counter(row["scope"] for row in picked)
        summary.append({
            "label": tag, "comments": len(picked), "titles": len({r["series_id"] for r in picked}),
            "first_episode_comments": by_scope["first_episode_comment"],
            "series_reviews": by_scope["series_review"],
        })
    with (HERE / "首批22部_逐条语义标签.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(*rows[0], *TAGS))
        writer.writeheader()
        writer.writerows({**row, **{tag: int(int(row["row_id"]) in ids) for tag, ids in memberships.items()}}
                         for row in rows)
    with (HERE / "首批22部_三维覆盖.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"{len(rows)} cards, {len(audience)} after excluding signed promotional text")
    for row in summary:
        print(*row.values(), sep="\t")


if __name__ == "__main__":
    summarize()
