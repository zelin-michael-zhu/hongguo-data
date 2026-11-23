"""Build entry-day own-performance inputs from already collected dated snapshots."""
import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
EXTENSION = OUTPUTS / "hongguo_watchlist_review_2026-11-21/extension"
HISTORY = OUTPUTS / "hongguo_free_pilot_2026-11-18/history"
FIELDS = ("date", "board", "id", "heat", "likes", "favorites", "rating")
BOARDS = ("ai", "comic", "hot", "real")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def pack_row(day, board, position, title):
    return dict(date=day, board=board, id=position["id"], heat=position.get("heat"),
                likes=title.get("like"), favorites=title.get("fav"), rating=title.get("rating"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-dir", type=Path,
                        help="Local checkout of drama-radar, path to data/snapshots/hongguo")
    options = parser.parse_args()
    archive = options.archive_dir
    if archive is None:
        search_root = Path(tempfile.gettempdir())
        archive = next(search_root.glob("hongguo_watchlist_archive_*/radar/data/snapshots/hongguo"))
    old_board = read_csv(HISTORY / "board_daily.csv")
    new_board = read_csv(EXTENSION / "new_rank_days.csv")
    old_drama = {(r["date"], r["id"]): r for r in read_csv(HISTORY / "drama_daily.csv")}
    expected = {(r["date"], r["board"], r["id"]): int(r["rank"]) for r in old_board + new_board}
    sources = json.loads((EXTENSION / "sources.json").read_text())
    extension_hashes = {s["day"]: s["sha256"] for s in sources if "sha256" in s}
    final_day = sources[-1]["day"]
    rows, manifest = [], []
    for day in sorted({d for d, _, _ in expected}):
        if day == final_day:
            last_dir = (EXTENSION / sources[-1]["source"]).parent
            info = json.loads((last_dir / "manifest.json").read_text())
            for board in BOARDS:
                assert info["boards"][board]["fresh_complete"]
                for position in json.loads((last_dir / (board + ".json")).read_text()):
                    assert expected[day, board, position["id"]] == position["rank"]
                    rows.append(pack_row(day, board, position, position))
            continue
        blob = (archive / (day + ".json")).read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        if day in extension_hashes:
            assert sha == extension_hashes[day]
        record = json.loads(blob)
        assert record["date"] == day and not record["stale"]
        manifest.append(dict(date=day, sha256=sha, fetched_at=record["fetched_at"],
                             source_type=record.get("imported_from", "native")))
        for board in BOARDS:
            for position in record["boards"][board]["items"]:
                sid = position["id"]
                assert expected[day, board, sid] == position["rank"]
                title = record["items"].get(sid, {})
                row = pack_row(day, board, position, title)
                if (day, sid) in old_drama:
                    export = old_drama[day, sid]
                    for key, field in (("likes", "like"), ("favorites", "fav"), ("rating", "rating")):
                        assert (row[key] is None and not export[field]) or float(row[key]) == float(export[field])
                rows.append(row)
    keys = {(r["date"], r["board"], r["id"]) for r in rows}
    assert keys == set(expected) and len(rows) == len(keys)
    for name, data, fields in (("own.csv", rows, FIELDS),
                               ("own_source_checks.csv", manifest, list(manifest[0]))):
        with (HERE / name).open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    for subset in (rows, [r for r in rows if r["date"] < final_day]):
        print(len(subset), dict(Counter(field for r in subset for field in FIELDS[3:] if r[field] is not None)))


if __name__ == "__main__":
    main()
