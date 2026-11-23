"""Measure membership changes on the same Hongguo top-K charts at two entity levels."""
import csv
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
PRIOR = OUTPUTS / "hongguo_watchlist_review_2026-11-21"
sys.path.insert(0, str(PRIOR))
from decision_audit import read_panel
from policies import BOARDS, read_rows

DEPTHS = (20, 50, 100)
COUNTS = ("title_entries", "unlinked_entries", "confirmed_entries", "within_present",
          "replacement_slots", "net_added_slots", "first_seen_titles", "returning_titles",
          "first_seen_groups", "returning_groups", "joint_extra_titles", "joint_arrival_groups",
          "group_entries_singleton_assumption", "unlinked_id_first", "unlinked_id_return")
DISTANCES = ("title_jaccard_distance", "group_jaccard_distance_unknown_as_singletons",
             "confirmed_title_jaccard_distance", "confirmed_group_jaccard_distance")


def write_table(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def distance(left, right):
    union = left | right
    return len(left ^ right) / len(union) if union else None


def groups_by_id(rows, depth):
    groups = defaultdict(set)
    for row in rows:
        if row["rank"] <= depth:
            groups[row["group"]].add(row["id"])
    return groups


def transition(previous, current, past_keys, prefix):
    past_ids = set().union(*previous.values())
    today_ids = set().union(*current.values())
    past_confirmed = {g for g in previous if g.startswith("g:")}
    today_confirmed = {g for g in current if g.startswith("g:")}
    known_past_ids = set().union(*(previous[g] for g in past_confirmed))
    known_today_ids = set().union(*(current[g] for g in today_confirmed))
    counts = Counter()
    details = []
    for group in sorted(current):
        today = current[group]
        before = previous.get(group, set())
        incoming, outgoing = today - before, before - today
        if not incoming:
            continue
        n, m = len(incoming), len(outgoing)
        counts["title_entries"] += n
        replacement = net_added = 0
        if group.startswith("i:"):
            kind = "unlinked_id"
            assert n == 1 and not before
            counts["unlinked_entries"] += 1
            counts["unlinked_id_return" if group in past_keys else "unlinked_id_first"] += 1
        else:
            counts["confirmed_entries"] += n
            if before:
                kind = "group_present_yesterday"
                replacement = min(n, m)
                net_added = n - replacement
                counts["within_present"] += n
                counts["replacement_slots"] += replacement
                counts["net_added_slots"] += net_added
            else:
                kind = "returning" if group in past_keys else "first_seen"
                counts[kind + "_titles"] += n
                counts[kind + "_groups"] += 1
                counts["joint_extra_titles"] += n - 1
                counts["joint_arrival_groups"] += int(n > 1)
        details.append(dict(**prefix, group_key=group, status=kind, previous_size=len(before),
                            current_size=len(today), n_enter=n, n_exit=m,
                            replacement_slots=replacement, net_added_slots=net_added,
                            incoming_ids="|".join(sorted(incoming)), outgoing_ids="|".join(sorted(outgoing)),
                            retained_ids="|".join(sorted(before & today)),
                            earlier_observed=group in past_keys,
                            previous_observed_date=past_keys.get(group, "")))
    counts["group_entries_singleton_assumption"] = len(set(current) - set(previous))
    assert counts["title_entries"] == len(today_ids - past_ids)
    assert counts["confirmed_entries"] + counts["unlinked_entries"] == counts["title_entries"]
    assert counts["within_present"] == counts["replacement_slots"] + counts["net_added_slots"]
    assert counts["confirmed_entries"] == counts["within_present"] + counts["first_seen_titles"] + counts["returning_titles"]
    assert counts["first_seen_groups"] + counts["returning_groups"] == len(today_confirmed - past_confirmed)
    assert counts["first_seen_titles"] + counts["returning_titles"] == counts["first_seen_groups"] + counts["returning_groups"] + counts["joint_extra_titles"]
    assert counts["title_entries"] - counts["group_entries_singleton_assumption"] == counts["within_present"] + counts["joint_extra_titles"]
    assert counts["unlinked_entries"] == counts["unlinked_id_return"] + counts["unlinked_id_first"]
    daily = dict(**prefix, **{key: counts[key] for key in COUNTS},
                 title_jaccard_distance=distance(past_ids, today_ids),
                 group_jaccard_distance_unknown_as_singletons=distance(set(previous), set(current)),
                 confirmed_title_jaccard_distance=distance(known_past_ids, known_today_ids),
                 confirmed_group_jaccard_distance=distance(past_confirmed, today_confirmed))
    return daily, details


def get_all_dates():
    original, dates, panels, _ = read_panel()
    # A positive observed on a partial day is still evidence of an earlier appearance.
    # Exclude all comparisons involving a partial day from the actual turnover denominator.
    roster = read_rows(OUTPUTS / "hongguo_expansion_2026-11-21/identity/identity_coverage.csv")
    keys = {r["series_id"]:r["series_group_id"] or r["old_sdk_album_id"] for r in roster}
    partial = defaultdict(list)
    history = read_rows(OUTPUTS / "hongguo_free_pilot_2026-11-18/history/board_daily.csv")
    for row in history:
        day, board = row["date"], row["board"]
        if day not in dates:
            sid = row["id"]
            row.update(rank=int(row["rank"]), group="g:"+keys[sid] if keys[sid] else "i:"+sid)
            partial[day, board].append(row)
    return set(original), set(dates), {**panels, **partial}


def main():
    old_dates, complete_dates, panels = get_all_dates()
    all_dates = sorted({d for d, _ in panels})
    pairs, ledger = [], []
    for board in BOARDS:
        for depth in DEPTHS:
            previous = {}
            past_keys = {}
            for day in all_dates:
                prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
                current = groups_by_id(panels[day, board], depth)
                if day in complete_dates and prev_day in complete_dates:
                    prefix = dict(date=day, prev_date=prev_day, board=board, k=depth)
                    daily, details = transition(previous, current, past_keys, prefix)
                    pairs.append(daily)
                    ledger.extend(details)
                past_keys.update(dict.fromkeys(current, day))
                previous = current
    summaries = []
    for label, dates in (("old35", old_dates), ("all39", complete_dates)):
        for board in BOARDS:
            for depth in DEPTHS:
                group = [r for r in pairs if r["date"] in dates and r["board"] == board and r["k"] == depth]
                assert len(group) == (33 if label == "old35" else 37)
                count = {k: sum(r[k] for r in group) for k in COUNTS}
                estimates = {k: mean(r[k] for r in group if r[k] is not None) for k in DISTANCES}
                n = count["title_entries"]
                summaries.append(dict(period=label, board=board, k=depth, adjacent_day_pairs=len(group),
                                      **count, within_present_share_all=count["within_present"]/n,
                                      inferred_group_entry_deficit_share=(n-count["group_entries_singleton_assumption"])/n,
                                      **estimates))
    write_table("turnover_summary.csv", summaries)
    write_table("paired_days.csv", pairs)
    write_table("entry_group_ledger.csv", ledger)
    originals = read_rows(OUTPUTS/"hongguo_three_pilots_2026-11-21/隔日入榜汇总.csv")
    for old in originals:
        if int(old["k"]) not in DEPTHS:
            continue
        now = next(r for r in summaries if r["period"] == "old35" and r["board"] == old["board"] and r["k"] == int(old["k"]))
        assert (now["title_entries"], now["within_present"], now["confirmed_entries"]) == tuple(int(old[k]) for k in ("entering_ids","confirmed_group_already_present","known_group_entrants"))
    return ledger, panels


if __name__ == "__main__":
    main()
