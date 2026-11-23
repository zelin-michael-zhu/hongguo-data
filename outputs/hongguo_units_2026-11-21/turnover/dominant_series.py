"""Sensitivity of matched-day Jaccard distances to the most repeated series."""
from collections import Counter
from datetime import date, timedelta
from statistics import mean

from replay import BOARDS, DEPTHS, distance, get_all_dates, groups_by_id, write_table


def main():
    _, dates, panels = get_all_dates()
    results = []
    for board in BOARDS:
        for depth in DEPTHS:
            slates = {day: groups_by_id(panels[day, board], depth) for day in sorted(dates)}
            extra = Counter()
            for slate in slates.values():
                extra.update({g: len(ids)-1 for g, ids in slate.items() if len(ids)>1})
            most = sorted(extra, key=lambda g: (-extra[g], g))[:1]
            for omit in ["", *most]:
                dd = []
                for day, grouped in slates.items():
                    prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
                    if prev_day not in slates:
                        continue
                    now = set(grouped) - {omit}
                    before = set(slates[prev_day]) - {omit}
                    now_ids = set().union(*(grouped[g] for g in now))
                    before_ids = set().union(*(slates[prev_day][g] for g in before))
                    dd.append((distance(before_ids, now_ids), distance(before, now)))
                title_mean, group_mean = map(mean, zip(*dd))
                results.append(dict(board=board, k=depth, excluded_group=omit,
                                    confirmed_extra_slots_contributed=extra[omit],
                                    adjacent_days=len(dd), title_jaccard_distance=title_mean,
                                    group_jaccard_distance=group_mean,
                                    group_minus_title_points=100*(group_mean-title_mean)))
    write_table("dominant_series_turnover.csv", results)


if __name__ == "__main__":
    main()
