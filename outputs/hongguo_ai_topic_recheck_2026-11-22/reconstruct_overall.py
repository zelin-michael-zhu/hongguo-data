"""Reconstruct the Hongguo website overall rankings from public type-chart heat."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median


HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
SOURCES = (
    OUTPUTS / "hongguo_free_pilot_2026-11-18/history/board_daily.csv",
    OUTPUTS / "hongguo_watchlist_review_2026-11-21/extension/new_rank_days.csv",
)
RANK_VALUES = OUTPUTS / "hongguo_franchise_forecast_2026-11-21/own.csv"
SOURCE_TYPES = OUTPUTS / "hongguo_franchise_forecast_2026-11-21/own_source_checks.csv"
TYPES = ("ai", "comic", "real")
LIMITS = (10, 20, 50, 100)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    assert rows
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load():
    measurements = {(r["date"], r["board"], r["id"]): r for r in read(RANK_VALUES)}
    provenance = {r["date"]: r["source_type"] for r in read(SOURCE_TYPES)}
    provenance["2026-11-21"] = "direct_website"
    days = defaultdict(lambda: defaultdict(dict))
    for path in SOURCES:
        for row in read(path):
            day, board, sid = row["date"], row["board"], row["id"]
            values = measurements[day, board, sid]
            assert sid not in days[day][board]
            days[day][board][sid] = dict(
                id=sid,
                title=row["title"].replace("\x00", " "),
                rank=int(row["rank"]),
                heat=int(values["heat"]) if values["heat"] else None,
            )
    return days, provenance


def complete(boards):
    return set(boards) == {"hot", *TYPES} and all(
        len(rows) == 100 and {row["rank"] for row in rows.values()} == set(range(1, 101))
        for rows in boards.values()
    )


def run():
    days, provenance = load()
    included = {day: boards for day, boards in days.items() if complete(boards)}
    reconstruction, gaps, ai_coverage, title_exposure = [], [], [], []
    for day, boards in sorted(included.items()):
        type_rows = [row for b in TYPES for row in boards[b].values()]
        by_type = {row["id"]: row for row in type_rows}
        assert len(type_rows) == len(by_type), f"Type-chart IDs overlap on {day}"
        scored = {sid: row for sid, row in by_type.items() if row["heat"] is not None}
        ordered = sorted(scored, key=lambda sid: (-scored[sid]["heat"], sid))
        ai, overall = boards["ai"], boards["hot"]
        ai_rank = {row["rank"]: row for row in ai.values()}
        overall_rank = {row["rank"]: row for row in overall.values()}
        for k in LIMITS:
            predicted_ids = ordered[:k]
            actual_ids = {overall_rank[r]["id"] for r in range(1, k + 1)}
            faults = {kind: 0 for kind in ("absent_from_type_charts", "type_heat_unavailable", "equal_at_cutoff", "other")}
            cutoff = scored[predicted_ids[-1]]["heat"]
            for sid in sorted(actual_ids - set(predicted_ids)):
                if sid not in by_type:
                    kind = "absent_from_type_charts"
                elif sid not in scored:
                    kind = "type_heat_unavailable"
                elif scored[sid]["heat"] == cutoff:
                    kind = "equal_at_cutoff"
                else:
                    kind = "other"
                faults[kind] += 1
                gaps.append(dict(date=day, cutoff_k=k, series_id=sid, mismatch_type=kind,
                                 overall_rank=overall[sid]["rank"], title=overall[sid]["title"],
                                 overall_heat=overall[sid]["heat"], type_heat=by_type.get(sid, {}).get("heat"),
                                 simulated_cutoff_heat=cutoff))
            reconstruction.append(dict(
                date=day, source=provenance[day], cutoff_k=k, scored_type_titles=len(scored),
                observed_overall_slots=len(actual_ids), matching_members=len(actual_ids & set(predicted_ids)),
                matching_positions=sum(sid == overall_rank[rank]["id"] for rank, sid in enumerate(predicted_ids, 1)),
                **faults,
            ))
        shared = ai.keys() & overall.keys()
        heat_pairs = [sid for sid in shared if ai[sid]["heat"] is not None and overall[sid]["heat"] is not None]
        row = dict(date=day, source=provenance[day], paired_titles=len(shared),
                   comparable_heat=len(heat_pairs), same_heat=sum(ai[sid]["heat"] == overall[sid]["heat"] for sid in heat_pairs),
                   ai20_heat=ai_rank[20]["heat"], overall20_heat=overall_rank[20]["heat"])
        for ai_k in (10, 20):
            ai_head = {ai_rank[rank]["id"] for rank in range(1, ai_k + 1)}
            for overall_k in LIMITS:
                row[f"ai{ai_k}_captured_by_overall{overall_k}"] = sum(
                    sid in overall and overall[sid]["rank"] <= overall_k for sid in ai_head
                )
            if ai_k == 20:
                row["overall_depth_to_cover_ai20"] = max(overall[sid]["rank"] for sid in ai_head) if ai_head <= overall.keys() else None
                title_exposure.extend(
                    dict(date=day, source=provenance[day], series_id=sid, title=ai[sid]["title"],
                         ai_rank=ai[sid]["rank"], overall_rank=overall.get(sid, {}).get("rank"),
                         ai_heat=ai[sid]["heat"], overall_heat=overall.get(sid, {}).get("heat"))
                    for sid in sorted(ai_head, key=lambda sid: ai[sid]["rank"])
                )
        ai_coverage.append(row)

    write_csv(HERE / "综合榜重建_逐日.csv", reconstruction)
    write_csv(HERE / "综合榜重建_差异榜位.csv", gaps)
    write_csv(HERE / "AI榜与综合榜_逐日覆盖.csv", ai_coverage)
    write_csv(HERE / "AI榜前二十_逐剧对照.csv", title_exposure)
    report = {"calendar_dates": len(days), "complete_dates": len(included),
              "excluded_incomplete_dates": sorted(days.keys() - included.keys())}
    for key in ("full", "exclude_migrated"):
        rec = [r for r in reconstruction if key == "full" or r["source"] != "hongguo-radar"]
        coverage = [r for r in ai_coverage if key == "full" or r["source"] != "hongguo-radar"]
        valid_thresholds = [r for r in coverage if r["ai20_heat"] is not None and r["overall20_heat"] is not None]
        rows_ai20 = [r for r in title_exposure if key == "full" or r["source"] != "hongguo-radar"]
        depth = [r["overall_depth_to_cover_ai20"] for r in coverage if r["overall_depth_to_cover_ai20"] is not None]
        by_k = {}
        for k in LIMITS:
            rows = [r for r in rec if r["cutoff_k"] == k]
            by_k[k] = dict(
                days=len(rows),
                complete_member_match_days=sum(r["matching_members"] == k for r in rows),
                matched_members=sum(r["matching_members"] for r in rows),
                matched_positions=sum(r["matching_positions"] for r in rows),
                observed_slots=sum(r["observed_overall_slots"] for r in rows),
                **{f: sum(r[f] for r in rows) for f in ("absent_from_type_charts", "type_heat_unavailable", "equal_at_cutoff", "other")},
            )
        report[key] = dict(
            reconstruction=by_k,
            comparable_ai_overall_heat=sum(r["comparable_heat"] for r in coverage),
            same_ai_overall_heat=sum(r["same_heat"] for r in coverage),
            ai_head_days=len(coverage), ai_head_coverage={
                f"ai{ai_k}_overall{overall_k}": sum(r[f"ai{ai_k}_captured_by_overall{overall_k}"] for r in coverage)
                for ai_k in (10, 20) for overall_k in LIMITS
            },
            distinct_ai20_titles=len({r["series_id"] for r in rows_ai20}),
            distinct_ai20_captured_at_least_once_by_overall={
                k: len({r["series_id"] for r in rows_ai20 if r["overall_rank"] is not None and r["overall_rank"] <= k})
                for k in LIMITS
            },
            daily_overall_depth_to_capture_ai20=dict(
                min=min(depth), median=median(depth), max=max(depth), days_with_coverage=len(depth)
            ),
            threshold_valid_days=len(valid_thresholds),
            median_combined_minus_ai_heat_at_20=median(r["overall20_heat"] - r["ai20_heat"] for r in valid_thresholds),
            median_combined_over_ai_heat_at_20=median(r["overall20_heat"] / r["ai20_heat"] for r in valid_thresholds),
        )
    assert report["full"]["reconstruction"][20]["observed_slots"] == 20 * len(included)
    (HERE / "综合榜重建_汇总.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
