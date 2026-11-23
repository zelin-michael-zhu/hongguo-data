"""Freeze the three forecasts and compare their later seven-day AI Top 20 outcomes."""
import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
import hashlib
import io
import json
import math
import os
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
DECISION = date(2026, 11, 21)
FUTURE_DAYS = [DECISION + timedelta(days=i) for i in range(1, 8)]
FEATURES = HERE / "AI榜22部逐剧信号.csv"
BASELINE = HERE / "board_only_baseline.csv"
BROAD_BASELINE = HERE / "11月21日两种数值基准.csv"
LOCK = HERE / "11月21日三种选法_冻结.csv"
PROTOCOL = HERE / "11月21日三种选法_口径.json"
MODEL_NAMES = ("board", "positive", "chase")
WEIGHT = 0.25
SIZES = (5, 10)


class IncompleteWindow(ValueError):
    """At least one forecast date cannot be evaluated yet."""


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    keyed = {row["series_id"]: row for row in rows}
    if len(rows) != len(keyed):
        raise ValueError(f"Duplicate series ID in {path.name}")
    return keyed


def csv_bytes(rows):
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode("utf-8-sig")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def write_once(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Existing frozen file differs: {path.name}")
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as scratch:
        temp = Path(scratch.name)
        try:
            scratch.write(content)
            scratch.flush()
            os.fsync(scratch.fileno())
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.read_bytes() != content:
                    raise ValueError(f"Existing frozen file differs: {path.name}")
        finally:
            temp.unlink(missing_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentiles(by_id, column):
    """Use midranks so tied shares receive the same contribution."""
    ties = defaultdict(list)
    for sid, row in by_id.items():
        value = float(row[column])
        if not math.isfinite(value):
            raise ValueError(f"Invalid {column} for series {sid}")
        ties[value].append(sid)
    n = len(by_id)
    ranks = {}
    offset = 0
    for value in sorted(ties):
        group = ties[value]
        percentile = (offset + (len(group) - 1) / 2) / (n - 1)
        ranks.update({sid: percentile for sid in group})
        offset += len(group)
    return ranks


def sort_models(base, positive, chase, raw_ranks, prefix):
    scores = {
        sid: (score, score + WEIGHT * positive[sid],
              score + WEIGHT * positive[sid] + WEIGHT * chase[sid])
        for sid, score in base.items()
    }
    ranks = {}
    for i, model in enumerate(MODEL_NAMES):
        ordered = sorted(base, key=lambda sid: (-scores[sid][i], -base[sid], raw_ranks[sid], sid))
        ranks[model] = {sid: pos for pos, sid in enumerate(ordered, 1)}
    return {
        sid: {f"{prefix}{model}_position": ranks[model][sid] for model in MODEL_NAMES}
        for sid in base
    }


def frozen_rows(features, board, broad):
    if not (len(features) == 22 and features.keys() == board.keys() == broad.keys()):
        raise ValueError("The frozen November 21 cohort must be identical across all three inputs")
    expected_window = (str(FUTURE_DAYS[0]), str(FUTURE_DAYS[-1]))
    for sid, row in features.items():
        window = row["forecast_window_start"], row["forecast_window_end"]
        if (window != expected_window or row["future_same_board_top20"]
            or broad[sid]["date"] != str(DECISION)
            or broad[sid]["future_same_board_top20"]):
            raise ValueError(f"Invalid outcome-free forecast inputs for {sid}")
    base = percentiles(board, "board_only_score")
    broad_base = percentiles(broad, "metrics_model_score")
    positive = percentiles(features, "series_positive_share_nonpromo")
    chase = percentiles(features, "series_chase_share_nonpromo")
    raw_ranks = {sid: int(row["rank"]) for sid, row in features.items()}
    main = sort_models(base, positive, chase, raw_ranks, "")
    sensitivity = sort_models(broad_base, positive, chase, raw_ranks, "sensitivity_")
    return [
        dict(series_id=sid, title=features[sid]["title"], forecast_date=str(DECISION),
             forecast_window_start=expected_window[0], forecast_window_end=expected_window[1],
             chart_rank=raw_ranks[sid], chart_age=features[sid]["same_board_age"],
             board_score=board[sid]["board_only_score"], board_percentile=base[sid],
             series_nonpromo_n=features[sid]["series_nonpromo_n"],
             series_positive_share=features[sid]["series_positive_share_nonpromo"],
             series_chase_share=features[sid]["series_chase_share_nonpromo"],
             positive_percentile=positive[sid], chase_percentile=chase[sid],
             **main[sid], **sensitivity[sid])
        for sid in sorted(features, key=lambda sid: main[sid]["board_position"])
    ]


def freeze(archive):
    rows = frozen_rows(*(read_csv(path) for path in (FEATURES, BASELINE, BROAD_BASELINE)))
    payload = csv_bytes(rows)
    if PROTOCOL.exists():
        existing = json.loads(PROTOCOL.read_text())
        if existing["lock_sha256"] != hashlib.sha256(payload).hexdigest():
            raise ValueError("Cannot replace forecasts already frozen")
        write_once(LOCK, payload)
        print(f"Existing forecast freeze verified for {len(rows)} titles")
        return
    now = datetime.now(ZONE)
    if now.date() > FUTURE_DAYS[0] or any((archive / str(day) / "chart.json").exists() for day in FUTURE_DAYS):
        raise ValueError("Freeze must precede the first observed forecast date")
    protocol = dict(frozen_at_sh=now.isoformat(timespec="seconds"),
                    original_text_date=str(DECISION), window=[str(d) for d in FUTURE_DAYS],
                    primary_k=SIZES[0], secondary_k=SIZES[1],
                    board_model="Temporally trained historical baseline using board fields only",
                    board_score="B", plus_positive="B + 0.25 P", plus_chase="B + 0.25 P + 0.25 C",
                    text_features="P = whole-series clear-positive share, C = whole-series explicit chase intent share",
                    denominator="Visible whole-series preview text after excluding explicit creator or promo voice",
                    normalization="Midrank percentiles within the 22 titles, highest value = 1 when untied",
                    tie_break="Baseline percentile descending, then current AI rank ascending, then series ID",
                    sensitivity="Broader frozen historical numerical baseline, same text weights",
                    days_until_first_top20="Calendar days from the original 21 November input snapshot",
                    status="First held-out cohort; fixed-weight ranking experiment, no text fitting",
                    input_sha256={p.name: digest(p) for p in (FEATURES, BASELINE, BROAD_BASELINE)},
                    lock_sha256=hashlib.sha256(payload).hexdigest())
    write_once(LOCK, payload)
    write_once(PROTOCOL, json_bytes(protocol))
    print(f"Frozen {len(rows)} titles across three rules: {LOCK.name}")


def read_charts(archive):
    if datetime.now(ZONE).date() < FUTURE_DAYS[-1]:
        raise IncompleteWindow(f"Observation window is open through {FUTURE_DAYS[-1]} Shanghai time")
    day_ranks, chart_sources, missing = {}, {}, []
    for day in FUTURE_DAYS:
        source = archive / day.isoformat() / "chart.json"
        if not source.exists():
            missing.append(str(day))
            continue
        payload = json.loads(source.read_text())
        completed = datetime.fromisoformat(payload["completed_at"])
        if payload["date"] != str(day) or completed.tzinfo is None or completed.astimezone(ZONE).date() != day:
            raise IncompleteWindow(f"Invalid observation date in {source}")
        pages = payload["pages"]
        if sorted(int(p["page"]) for p in pages) != list(range(1, 6)) or any(
            p["label_date"] != str(day) for p in pages
        ):
            raise IncompleteWindow(f"Missing or stale AI chart page in {source}")
        rows = payload["records"]
        observed = {str(r["id"]): int(r["rank"]) for r in rows}
        if len(rows) != 100 or len(observed) != 100 or set(observed.values()) != set(range(1, 101)):
            raise IncompleteWindow(f"Missing or duplicated AI chart ranks in {source}")
        day_ranks[day] = observed
        chart_sources[str(day)] = {"path": str(source), "sha256": digest(source)}
    if missing:
        raise IncompleteWindow(f"Missing dated AI chart snapshots: {', '.join(missing)}")
    return day_ranks, chart_sources


def chosen_for(rows, position_column, k):
    return sorted((row for row in rows if int(row[position_column]) <= k), key=lambda row: int(row[position_column]))


def hits_for(rows):
    return {row["series_id"]: row for row in rows if row["hit_top20"]}


def summary_metrics(chosen):
    hits = list(hits_for(chosen).values())
    lead = [row["days_until_first_top20"] for row in hits]
    return dict(slots=len(chosen), hits=len(hits), precision=len(hits) / len(chosen),
                mean_lead_days=mean(lead) if lead else None, median_lead_days=median(lead) if lead else None,
                ranked_titles=[row["title"] for row in chosen],
                hit_titles=[row["title"] for row in hits])


def compare_hits(previous, current):
    prev_hits, curr_hits = hits_for(previous), hits_for(current)
    return dict(delta_hits=len(curr_hits) - len(prev_hits),
                added_hits=[{"title": r["title"], "first_top20_date": r["first_top20_date"],
                             "lead_days": r["days_until_first_top20"]} for sid, r in curr_hits.items() if sid not in prev_hits],
                lost_hits=[{"title": r["title"], "first_top20_date": r["first_top20_date"],
                            "lead_days": r["days_until_first_top20"]} for sid, r in prev_hits.items() if sid not in curr_hits])


def evaluate_rows(frozen, day_ranks):
    results = []
    for sid, row in frozen.items():
        ranks = [day_ranks[day].get(sid) for day in FUTURE_DAYS]
        hit_dates = [day for day, rank in zip(FUTURE_DAYS, ranks) if rank is not None and rank <= 20]
        first = hit_dates[0] if hit_dates else None
        results.append(dict(**row, **{f"ai_rank_{day}": rank if rank is not None else ""
                                      for day, rank in zip(FUTURE_DAYS, ranks)},
                            hit_top20=int(first is not None), first_top20_date=str(first) if first else "",
                            days_until_first_top20=(first - DECISION).days if first else "",
                            number_of_top20_days=len(hit_dates),
                            best_observed_ai_rank=min((rank for rank in ranks if rank is not None), default="")))
    summaries = {}
    for scope, prefix in (("primary", ""), ("sensitivity", "sensitivity_")):
        summaries[scope] = {}
        for k in SIZES:
            chosen = {m: chosen_for(results, f"{prefix}{m}_position", k) for m in MODEL_NAMES}
            summaries[scope][str(k)] = dict(
                models={m: summary_metrics(rows) for m, rows in chosen.items()},
                increment_positive=compare_hits(chosen["board"], chosen["positive"]),
                increment_chase=compare_hits(chosen["positive"], chosen["chase"]))
    return results, summaries


def evaluate(archive):
    day_ranks, sources = read_charts(archive)
    protocol = json.loads(PROTOCOL.read_text())
    if digest(LOCK) != protocol["lock_sha256"]:
        raise ValueError("Frozen forecasts do not match the pre-outcome manifest")
    results, summaries = evaluate_rows(read_csv(LOCK), day_ranks)
    total_hits = sum(row["hit_top20"] for row in results)
    write_once(HERE / "11月28日三种选法_逐剧结局.csv", csv_bytes(results))
    write_once(HERE / "11月28日三种选法_结果.json", json_bytes(
        dict(evaluation=True, n=len(results), eligible_hits=total_hits, chart_sources=sources,
             frozen_forecasts_sha256=protocol["lock_sha256"], **summaries)))
    primary = summaries["primary"]
    for k in SIZES:
        stat = primary[str(k)]
        print(f"Top {k}: " + " | ".join(f"{m} {v['hits']}/{v['slots']}" for m, v in stat["models"].items())
              + f" | incremental chase hits {stat['increment_chase']['delta_hits']:+d}")
    print(f"{total_hits}/{len(results)} eligible titles reached the AI Top 20 in the seven-day window")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--evaluate", action="store_true")
    parser.add_argument("--archive-dir", type=Path, default=HERE / "daily")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.archive_dir)
    else:
        try:
            evaluate(args.archive_dir)
        except IncompleteWindow as exc:
            parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
