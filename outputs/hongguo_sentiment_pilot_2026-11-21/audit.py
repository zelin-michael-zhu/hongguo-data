"""Audit saved website previews without contacting the platform or exporting users or text."""
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
OLD = OUT / "hongguo_free_pilot_2026-11-18"
MID = OUT / "hongguo_topic_implementation_2026-11-19/reviews"
NEW = OUT / "hongguo_expansion_2026-11-21"
BREAKOUT = OUT / "hongguo_breakout_2026-11-21"
SH = ZoneInfo("Asia/Shanghai")
REVIEW, EP = "series_review", "first_episode_comment"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def parsed(scope, sid, stamp, content, likes, collected, rating="", source_id=""):
    return dict(scope=scope, sid=sid, stamp=str(stamp), text=normalized(content),
                likes=int(likes), collected=collected, rating=str(rating), source_id=source_id)


def read_samples():
    nov18 = [parsed(REVIEW if r["scope"] == REVIEW else EP, r["series_id"], r["create_time_raw"],
                    r["content"], r["digg_count"], r["collected_at"], r["rating"], r["comment_id"])
             for r in read(OLD / "comments_preview.csv")]
    nov19 = []
    for folder in ("sanitized_captures", "calibration_today"):
        for path in sorted((MID / folder).glob("*.json")):
            source = json.loads(path.read_text())
            for r in source["reviews"]:
                nov19.append(parsed(REVIEW, source["series_id"], r["create_time"], r["text"],
                                    r["digg_count"], source["sample_time"], r["review_rating"]))
    nov21 = [parsed(r["scope"], r["series_id"], r["create_time_raw"], r["text"],
                    r["digg_count"], r["collected_at_utc"], r["rating"], r["source_comment_id"])
             for r in read(NEW / "reviews_preview.csv")]
    return {"2026-11-18": nov18, "2026-11-19": nov19, "2026-11-21": nov21}


def signatures(rows):
    return {(r["stamp"], r["text"]): r["likes"] for r in rows}


def overlap(samples, left, right, scope, title_names):
    pages = []
    for day in (left, right):
        by_id = defaultdict(list)
        for r in samples[day]:
            if scope == r["scope"]:
                by_id[r["sid"]].append(r)
        pages.append(by_id)
    shared = sorted(pages[0].keys() & pages[1].keys())
    matched, old_rows, new_rows, changed_likes, identical, examples = 0, 0, 0, 0, 0, []
    for sid in shared:
        a, b = (signatures(group[sid]) for group in pages)
        common = a.keys() & b.keys()
        old_rows += len(a)
        new_rows += len(b)
        matched += len(common)
        identical += a.keys() == b.keys()
        changed_likes += sum(a[k] != b[k] for k in common)
        examples.append(dict(title=title_names[sid], rows_before=len(a), retained=len(common),
                             rows_after=len(b)))
    return dict(shared_titles=len(shared), fingerprints_before=old_rows,
                fingerprints_after=new_rows, common_fingerprints=matched,
                common_with_different_likes=changed_likes, pages_same_set=identical,
                example_most_turnover=min(examples, key=lambda r:r["retained"]) if examples else None)


def main():
    samples = read_samples()
    cov = read(NEW / "series_coverage.csv")
    titles = {r["series_id"]: r["catalog_title"] for r in cov}
    report = {"daily_scopes": {}, "overlap": {}}
    for day, rows in samples.items():
        for scope in (REVIEW, EP):
            batch = [r for r in rows if r["scope"] == scope]
            sizes = Counter(r["sid"] for r in batch)
            counts = Counter((r["sid"], r["stamp"], r["text"]) for r in batch)
            day_stamps = set()
            bad_times = missing_collect = 0
            pubdates = []
            for r in batch:
                published = datetime.fromtimestamp(int(r["stamp"]), timezone.utc)
                pubdates.append(published.astimezone(SH).date().isoformat())
                if r["collected"]:
                    captured = datetime.fromisoformat(r["collected"])
                    day_stamps.add(captured.astimezone(SH).date().isoformat())
                    bad_times += published > captured
                else:
                    missing_collect += 1
            assert day_stamps <= {day}
            report["daily_scopes"][day + "/" + scope] = dict(
                titles=len(sizes), rows=len(batch), rows_per_page_histogram=dict(sorted(Counter(sizes.values()).items())),
                excess_duplicate_fingerprints=sum(n-1 for n in counts.values() if n>1),
                distinct_source_ids=len({r["source_id"] for r in batch if r["source_id"]}),
                missing_exact_collection_time=missing_collect, publication_after_capture=bad_times,
                min_publication_date=min(pubdates, default=None), max_publication_date=max(pubdates, default=None))
    for left, right in (("2026-11-18","2026-11-19"),("2026-11-18","2026-11-21"),
                        ("2026-11-19","2026-11-21")):
        for scope in (REVIEW, EP):
            report["overlap"][f"{left}_{right}/{scope}"] = overlap(samples, left, right, scope, titles)

    catalogue = read(OLD / "history/catalog.csv")
    episodes = read(OLD / "episodes.csv")
    danmaku = read(OLD / "danmaku_sample.csv")
    report["catalogue_rows"] = len(catalogue)
    report["episodes_numerics_11_18"] = dict(rows=len(episodes), series=len({r["series_id"] for r in episodes}))
    report["danmaku_11_18"] = dict(rows=len(danmaku), series=len({r["series_id"] for r in danmaku}),
                                   episode_ids=len({r["episode_id"] for r in danmaku}))
    for scope, n, total in ((REVIEW, "series_reviews_with_text", "series_reviews_total"),
                            (EP, "first_episode_comments_with_text", "first_episode_comments_total")):
        pages = [r for r in cov if r[total] != ""]
        report["daily_scopes"]["2026-11-21/" + scope].update(
            total_reported_sum=sum(int(r[total]) for r in pages),
            pages_preview_equals_reported_total=sum(int(r[n]) == int(r[total]) for r in pages))
    ordered = read(MID / "render_order_audit.csv")
    report["nov19_repeat_render_checks"] = len(ordered)
    rankpanel = read(BREAKOUT / "broad_panel.csv")
    report["same_day_previously_never_top20_first_chart_age_1to3"] = {}
    for day in samples:
        candidates = [r for r in rankpanel if r["date"] == day and int(r["age"]) <= 3]
        ids = {r["id"] for r in candidates}
        counts = {scope: len({r["sid"] for r in samples[day] if r["scope"] == scope} & ids)
                  for scope in (REVIEW, EP)}
        report["same_day_previously_never_top20_first_chart_age_1to3"][day] = dict(
            eligible_unique_titles=len(ids), **counts)
    hist = read(OLD / "history/drama_daily.csv")
    hist_units = {(r["date"],r["id"]) for r in hist}
    snapshots = read(OUT / "hongguo_franchise_forecast_2026-11-21/own.csv")
    report["numeric_series"] = dict(history_days=len({r["date"] for r in hist}),
        history_title_days=len(hist_units), columns=list(hist[0]), extended_days=len({r["date"] for r in snapshots}),
        extended_board_rows=len(snapshots), extended_export_columns=list(snapshots[0]))
    report["age7_horizon_contains_mature_capture_days"] = sum(
        (date(2026,11,21)-date.fromisoformat(day)).days >= 7 for day in samples)
    report["cross_scope_simultaneous_same_title_stamp_text_11_21"] = len(set.intersection(
        *[{(r["sid"], r["stamp"], r["text"]) for r in samples["2026-11-21"] if r["scope"] == scope}
          for scope in (REVIEW, EP)]))
    grouped_stamps = defaultdict(set)
    for r in samples["2026-11-21"]:
        grouped_stamps[r["sid"], r["scope"], r["stamp"]].add(r["text"])
    report["same_series_scope_second_with_multiple_texts_11_21"] = sum(
        len(v)>1 for v in grouped_stamps.values())
    example_id = next(sid for sid,t in titles.items() if t=="持械入宋：第十一季")
    example = {}
    for day in ("2026-11-18", "2026-11-21"):
        seconds = [int(r["stamp"]) for r in samples[day] if r["scope"] == REVIEW and r["sid"] == example_id]
        example[day] = dict(n=len(seconds), published_by_nov18=sum(
            datetime.fromtimestamp(s, SH).date() <= date(2026,11,18) for s in seconds))
    report["example_historical_time_filter"] = dict(title=titles[example_id], snapshots=example)
    # Alternative question: stay below the cutoff on this named chart. Dates
    # since first appearance on any chart and on the same chart are different clocks.
    sys.path.insert(0, str(BREAKOUT))
    from panel import observed_charts, complete_dates
    daily_charts, boards = observed_charts()
    complete = complete_dates(boards, 100)
    first_any, first_same, previous_head = {}, {}, set()
    variants = {}
    for day, daily in sorted(daily_charts.items()):
        pools = {"first_any_chart": set(), "first_same_chart": set()}
        for sid, entries in daily.items():
            first_any.setdefault(sid, day)
            for board, row in entries.items():
                pair = (sid, board)
                first_same.setdefault(pair, day)
                if row["rank"]<=20:
                    previous_head.add(pair)
                if day not in complete or pair in previous_head:
                    continue
                if (day - first_any[sid]).days<=2:
                    pools["first_any_chart"].add(pair)
                if (day - first_same[pair]).days<=2:
                    pools["first_same_chart"].add(pair)
        ds = day.isoformat()
        if ds not in samples:
            continue
        for clock, pairs in pools.items():
            ids = {sid for sid,_ in pairs}
            matched = ids & {r["sid"] for r in samples[ds]}
            variants[ds + "/" + clock] = dict(eligible_board_title_pairs=len(pairs),
                eligible_distinct_titles=len(ids), titles_with_text=len(matched),
                matched_titles=sorted(titles[sid] for sid in matched))
    report["same_chart_top20_target_by_entry_clock"] = variants
    (HERE / "archive_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
