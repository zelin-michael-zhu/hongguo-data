"""Compare title and series occupancy within the same observed chart seats."""
import csv
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "hongguo_watchlist_review_2026-11-21"))
from decision_audit import BOARDS, read_panel


def write_csv(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def concentration(counter):
    n = counter.total()
    return sum(count * count for count in counter.values()) / (n * n)


def measured_seats(rows):
    items = Counter(row["id"] for row in rows)
    groups = Counter(row["group"] for row in rows)
    title_hhi = concentration(items)
    group_hhi = concentration(groups)
    assert group_hhi + 1e-12 >= title_hhi
    known_groups = sum(g.startswith("g:") for g in groups)
    return dict(seats=items.total(), distinct_titles=len(items), distinct_groups=len(groups),
                unknown_title_ids=sum(g.startswith("i:") for g in groups),
                minimum_distinct_groups=max(1,known_groups), maximum_distinct_groups=len(groups),
                known_seats=sum(count for group, count in groups.items() if group.startswith("g:")),
                title_hhi=title_hhi, group_hhi=group_hhi,
                effective_titles=1/title_hhi, effective_groups=1/group_hhi,
                top_title_share=max(items.values())/items.total(),
                top_group_share=max(groups.values())/items.total())


def run():
    old, full, panels, _ = read_panel()
    segments = {"old35": old, "new4": sorted(set(full) - set(old)), "all39": full}
    daily, summary, rankings = [], [], []
    for segment, dates in segments.items():
        for k in (20, 50, 100):
            for board in BOARDS:
                slates = {date: [r for r in panels[date, board] if r["rank"] <= k] for date in dates}
                redundant = Counter()
                examples = {}
                for slate in slates.values():
                    counts = Counter(row["group"] for row in slate)
                    redundant.update({g:count-1 for g, count in counts.items() if count>1})
                    for row in sorted(slate, key=lambda x:x["rank"]):
                        examples.setdefault(row["group"],row["title"])
                leaders = sorted(g for g, v in redundant.items() if v == max(redundant.values()))
                leader = leaders[0] if leaders else ""
                leader_extra = redundant.get(leader, 0)
                scenarios = ["all_with_singleton_unknown", "known_only"]
                if leader:
                    scenarios.append("exclude_top_repeater")
                for scenario in scenarios:
                    days, all_rows = [], []
                    for date, slate in slates.items():
                        seats = slate
                        if scenario == "exclude_top_repeater":
                            seats = [r for r in slate if r["group"] != leader]
                        if scenario == "known_only":
                            seats = [r for r in slate if r["group"].startswith("g:")]
                        if not seats:
                            continue
                        measures = measured_seats(seats)
                        assert measures["seats"] == measures["distinct_titles"]
                        assert math.isclose(measures["title_hhi"],1/len(seats))
                        days.append(measures)
                        all_rows.extend(seats)
                        daily.append(dict(period=segment, board=board, depth=k, scenario=scenario,
                                          date=date, **measures))
                    pool = measured_seats(all_rows)
                    summary.append(dict(period=segment, board=board, depth=k, scenario=scenario,
                        available_days=len(days), observed_panel_seats_before_filter=len(dates)*k,
                        analyzed_seats=pool["seats"], known_seat_share=pool["known_seats"]/pool["seats"],
                        day_mean_titles=mean(r["distinct_titles"] for r in days),
                        day_mean_groups=mean(r["distinct_groups"] for r in days),
                        day_mean_title_hhi=mean(r["title_hhi"] for r in days),
                        day_mean_group_hhi=mean(r["group_hhi"] for r in days),
                        day_mean_effective_titles=mean(r["effective_titles"] for r in days),
                        day_mean_effective_groups=mean(r["effective_groups"] for r in days),
                        pooled_distinct_titles=pool["distinct_titles"], pooled_distinct_groups=pool["distinct_groups"],
                        pooled_unknown_title_ids=pool["unknown_title_ids"],
                        pooled_minimum_groups=pool["minimum_distinct_groups"], pooled_maximum_groups=pool["maximum_distinct_groups"],
                        pooled_title_hhi=pool["title_hhi"], pooled_group_hhi=pool["group_hhi"],
                        pooled_effective_titles=pool["effective_titles"],pooled_effective_groups=pool["effective_groups"],
                        pooled_top_title_share=pool["top_title_share"], pooled_top_group_share=pool["top_group_share"],
                        confirmed_additional_slots=sum(r["seats"]-r["distinct_groups"] for r in days),
                        unfiltered_top_repeater=leader, example_title=examples.get(leader,""),
                        unfiltered_others_tied_for_first="|".join(leaders[1:]),
                        unfiltered_top_repeater_extra=leader_extra, unfiltered_total_extra=redundant.total(),
                        unfiltered_top_share_among_confirmed_extra=leader_extra/redundant.total() if redundant else ""))
            for scenario in ("all_with_singleton_unknown", "known_only", "exclude_top_repeater"):
                group = [r for r in summary if (r["period"],r["depth"],r["scenario"]) == (segment,k,scenario)]
                for a,b in combinations(group,2):
                    tdelta=a["pooled_title_hhi"]-b["pooled_title_hhi"]
                    gdelta=a["pooled_group_hhi"]-b["pooled_group_hhi"]
                    rankings.append(dict(period=segment,depth=k,scenario=scenario,board_a=a["board"],board_b=b["board"],
                                         title_hhi_a_minus_b=tdelta,group_hhi_a_minus_b=gdelta,
                                         strict_order_reversal=int(tdelta*gdelta<0)))
    write_csv("daily_concentration.csv",daily)
    write_csv("concentration_summary.csv",summary)
    write_csv("pairwise_board_reversals.csv",rankings)


if __name__ == "__main__":
    run()
