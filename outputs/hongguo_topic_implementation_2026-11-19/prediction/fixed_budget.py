"""Replay a fixed 10-place monitoring decision using previously saved, unrounded forecasts."""
import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
SCORES = OUT.parents[1] / "hongguo_research_review_2026-11-19/evidence/prediction_pilot_rows.csv"
ARCHIVE = OUT.parents[1] / "hongguo_free_pilot_2026-11-18/history/board_daily.csv"
BUDGET = 10
MODELS = {"base": "rank_trend_probability", "extended": "extended_probability"}

def load(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def save(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def rollup(entries):
    result = {key: sum(e[key] for e in entries) for key in (
        "available", "actual_exits", "slots_each", "base_hits", "extended_hits", "shared_slots", "shared_hits",
        "base_cutoff_tie", "extended_cutoff_tie")}
    result["extra_hits"] = result["extended_hits"] - result["base_hits"]
    shared, slots = result["shared_slots"], result["slots_each"]
    result["overlap_share"] = shared / slots
    result["jaccard_pooled"] = shared / (2 * slots - shared)
    return result

def quantile(values, q):
    pos = q * (len(values) - 1)
    i = math.floor(pos)
    return values[i] + (pos - i) * (values[math.ceil(pos)] - values[i])

def block_diagnostic(deltas, block):
    # Circular moving blocks; each day keeps all boards together. Enumerate starts exactly for n=10.
    n = len(deltas)
    assert n == 10
    enough = math.ceil(n / block)
    sims = sorted(sum(deltas[(starts[j // block] + j % block) % n] for j in range(n)) / n
                  for starts in itertools.product(range(n), repeat=enough))
    return {"block_days": block, "combinations": len(sims), "mean_extra_hits_per_day_percentile_2_5": quantile(sims, 0.025),
            "mean_extra_hits_per_day_percentile_97_5": quantile(sims, 0.975)}

preds = load(SCORES)
all_ids = defaultdict(set)
for row in load(ARCHIVE):
    all_ids[(row["date"], row["board"])].add(row["id"])
groups = defaultdict(list)
for row in preds:
    target, origin, board, identity = (row[k] for k in ("target_date", "forecast_origin", "board", "series_id"))
    assert date.fromisoformat(origin) + timedelta(days=1) == date.fromisoformat(target)
    assert len(all_ids[origin,board]) == len(all_ids[target,board]) == 100
    assert identity in all_ids[origin,board]
    assert int(row["exit_next_day"]) == int(identity not in all_ids[target,board])
    groups[target,board].append(row)
records, picks = [], []
for (target,board), rows in sorted(groups.items()):
    indexed = {r["series_id"]: r for r in rows}
    assert len(rows) == len(indexed) == 100
    scores = {}
    ties = {}
    for model, key in MODELS.items():
        ranked = sorted(rows, key=lambda r: (-float(r[key]), int(r["series_id"])))
        assert all(0 <= float(r[key]) <= 1 for r in rows)
        scores[model] = {r["series_id"]:i+1 for i,r in enumerate(ranked[:BUDGET])}
        ties[model] = int(float(ranked[BUDGET-1][key]) == float(ranked[BUDGET][key]))
    shared = scores["base"].keys() & scores["extended"].keys()
    def hits(ids):
        return sum(int(indexed[i]["exit_next_day"]) for i in ids)
    for i in sorted(scores["base"].keys() | scores["extended"].keys(), key=int):
        r = indexed[i]
        picks.append({key:r[key] for key in ("forecast_origin","target_date","board","series_id","exit_next_day","rank_trend_probability","extended_probability")}
                     | {"baseline_selected_rank":scores["base"].get(i,""), "extended_selected_rank":scores["extended"].get(i,"")})
    info = {"available":len(rows), "actual_exits":hits(indexed), "slots_each":BUDGET, "base_hits":hits(scores["base"]),
            "extended_hits":hits(scores["extended"]), "shared_slots":len(shared), "shared_hits":hits(shared),
            "base_cutoff_tie":ties["base"], "extended_cutoff_tie":ties["extended"]}
    records.append({"target_date":target, "board":board} | rollup([info]))
daily = [{"target_date":d} | rollup([r for r in records if r["target_date"]==d]) for d in sorted({r["target_date"] for r in records})]
boards = [{"board":b} | rollup([r for r in records if r["board"]==b]) for b in sorted({r["board"] for r in records})]
save("by_day_board.csv",records)
save("by_day.csv",daily)
save("by_board.csv",boards)
save("selected_ids.csv",picks)
out = rollup(records)
delta = [r["extra_hits"] for r in daily]
out.update({"input_score_sha256":hashlib.sha256(SCORES.read_bytes()).hexdigest(), "labels_verified_against_archived_ids":len(preds),
            "dates":len(daily), "day_boards":len(records), "ties_rule":"Numeric ID ascending for equal unrounded predicted probability",
            "day_wins_ties_losses":[sum(x>0 for x in delta),sum(x==0 for x in delta),sum(x<0 for x in delta)],
            "mean_extra_hits_per_day":sum(delta)/len(delta),
            "leave_one_date_out_mean_range":[min((sum(delta)-d)/(len(delta)-1) for d in delta),max((sum(delta)-d)/(len(delta)-1) for d in delta)],
            "circular_block_bootstrap_sensitivity":[block_diagnostic(delta,b) for b in (2,3)]})
(OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False))
