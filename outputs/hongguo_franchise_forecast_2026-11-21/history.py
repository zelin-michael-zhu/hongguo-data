"""Build at-entry sibling histories, then attach outcomes from later chart snapshots."""

import csv
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(OUT / "hongguo_watchlist_review_2026-11-21"))
sys.path.insert(0, str(OUT / "hongguo_expansion_2026-11-21/identity"))
sys.path.insert(0, str(OUT / "hongguo_units_2026-11-21/turnover"))
from decision_audit import read_panel
from explicit_seasons import MARKER, season_number
from policies import BOARDS, read_rows
from replay import get_all_dates
from title_keys import explicit_key


def move(day, offset):
    return (date.fromisoformat(day) + timedelta(days=offset)).isoformat()


def season_from_title(title):
    markers = MARKER.findall(unicodedata.normalize("NFKC", title))
    return season_number(markers[0]) if len(markers) == 1 else ""


def encode_history(day, board, sid, group, today, earlier_groups, complete, num):
    sibling_fields = ("active_count", "best_rank", "momentum", "seasons_observed", "prior_chart_days",
                      "today_count", "recent_best_rank", "active_streak")
    result = dict(linked=int(not group.startswith("i:")), season_number=num)
    if not result["linked"]:
        return dict(result, **dict.fromkeys(sibling_fields, ""))
    seen = earlier_groups[board].get(group, {})
    siblings = {k: values for k, values in seen.items() if k != sid}
    ranks_by_day = defaultdict(list)
    for visits in siblings.values():
        for d, rank in visits.items():
            assert d < day
            ranks_by_day[d].append(rank)
    previous_seats = ranks_by_day.get(move(day,-1), [])
    prior7 = [move(day,-i) for i in range(1,8)]
    recent_ranks = [rank for d in prior7 for rank in ranks_by_day.get(d, [])]
    result.update(active_count=len(previous_seats), best_rank=min(previous_seats,default=""),
                  seasons_observed=len(siblings), prior_chart_days=len(ranks_by_day),
                  today_count=sum(other != sid for other in today.get(group, [])),
                  recent_best_rank=min(recent_ranks, default=""))
    # A complete list with no sibling contributes zero visibility score, not an invented outside rank.
    result["momentum"] = ""
    if set(prior7[:6]).issubset(complete):
        prominence = [101-min(ranks_by_day[d]) if ranks_by_day.get(d) else 0 for d in prior7[:6]]
        result["momentum"] = round((sum(prominence[:3])-sum(prominence[3:]))/3, 6)
    streak = 0
    while move(day,-streak-1) in complete and ranks_by_day.get(move(day,-streak-1)):
        streak += 1
    result["active_streak"] = streak
    return result


def collect_entries(last_day=None):
    _, _, _, archived_proxy = read_panel()
    _, complete, panels = get_all_dates()
    old = read_rows(OUT / "hongguo_watchlist_review_2026-11-21/identity/asof_groups.csv")
    original_names = {(r["date"],r["id"]):r["title_asof"] for r in old}
    dates = sorted({d for d,_ in panels if last_day is None or d <= last_day})
    complete = complete.intersection(dates)
    visited = {b:set() for b in BOARDS}
    history = {m:{b:defaultdict(lambda:defaultdict(dict)) for b in BOARDS} for m in ("asof","oracle")}
    first_proxy = {}
    entries, ranks, yesterday = [], {}, {}
    for index, day in enumerate(dates):
        before = move(day,-1)
        current = {b:{r["id"]:r for r in panels[day,b]} for b in BOARDS}
        today_titles = {}
        for b in sorted(BOARDS):
            for sid,r in current[b].items():
                today_titles.setdefault(sid,original_names.get((day,sid),r["title"]))
        for sid in today_titles:
            first_proxy.setdefault(sid,explicit_key(today_titles[sid],sid))
            assert first_proxy[sid] == archived_proxy[sid]
        for board in BOARDS:
            current_keys = {"asof":defaultdict(set), "oracle":defaultdict(set)}
            for sid, r in current[board].items():
                current_keys["asof"][first_proxy[sid]].add(sid)
                current_keys["oracle"][r["group"]].add(sid)
            ranks[day,board] = {sid:r["rank"] for sid,r in current[board].items()}
            if day not in complete or before not in complete:
                continue
            prior7 = [move(day,-n) for n in range(1,8)]
            for sid in sorted(current[board].keys()-yesterday[board].keys(),
                              key=lambda j:current[board][j]["rank"]):
                r = current[board][sid]
                title = today_titles[sid]
                num = season_from_title(title)
                event = dict(date=day,board=board,id=sid,title=title,group=r["group"],rank=r["rank"],
                             asof_group=first_proxy[sid],
                             entry_type="reentry" if sid in visited[board] else "first_observed",
                             prev_other_board=int(any(sid in yesterday[b] for b in BOARDS if b != board)),
                             same_day_other_board=int(any(sid in current[b] for b in BOARDS if b != board)),
                             simultaneous_new_other=int(any(sid in current[b] and sid not in yesterday[b]
                                                            for b in BOARDS if b != board)),
                             days_since_start=index, full_prior7=int(set(prior7).issubset(complete)),
                             complete_days_in_prior7=sum(d in complete for d in prior7),
                             prior7_has_partial=int(any(d in dates and d not in complete for d in prior7)))
                for mode, group in (("asof", first_proxy[sid]), ("oracle", r["group"])):
                    features = encode_history(day,board,sid,group,current_keys[mode],
                                              history[mode],complete,num)
                    event.update({mode+"_"+key:value for key,value in features.items()})
                entries.append(event)
        for b in BOARDS:
            visited[b].update(current[b])
            for sid,r in current[b].items():
                history["asof"][b][first_proxy[sid]][sid][day]=r["rank"]
                history["oracle"][b][r["group"]][sid][day]=r["rank"]
        yesterday = current
    return entries, ranks, complete


def attach_outcomes(rows,ranks,complete):
    for r in rows:
        day,b,sid = r["date"],r["board"],r["id"]
        follow = [move(day,n) for n in range(1,8)]
        r["full_future7"] = int(set(follow).issubset(complete))
        for key in ("days7","day7","top20_7","best_rank7"):
            r[key] = ""
        if r["full_future7"]:
            daily = [ranks[d,b].get(sid) for d in follow]
            observed = [rank for rank in daily if rank is not None]
            r.update(days7=len(observed),day7=int(daily[-1] is not None),
                     top20_7=int(any(n<=20 for n in observed)),best_rank7=min(observed,default=""))
        offset=1
        while move(day,offset) in complete and sid in ranks[move(day,offset),b]:
            offset+=1
        failure=int(move(day,offset) in complete)
        r.update(exit_time=offset if failure else offset-1,exit_observed=failure,
                 last_consecutive_day=move(day,offset-1))


def main():
    rows,ranks,complete = collect_entries()
    for cutoff in ("2026-10-23", "2026-11-11"):
        prefix,_,_ = collect_entries(last_day=cutoff)
        assert prefix == [r for r in rows if r["date"]<=cutoff]
    attach_outcomes(rows,ranks,complete)
    keys = {(r["date"],r["board"],r["id"]) for r in rows}
    assert len(keys)==len(rows)
    old=read_rows(OUT/"hongguo_entry_signal_2026-11-21/entry_events.csv")
    known_old={(r["date"],r["board"],r["id"]):r for r in old if r["complete_window"]=="1"}
    assert len(known_old)==len([r for r in rows if r["full_future7"]])==1090
    for r in rows:
        if r["full_future7"]:
            prev=known_old[r["date"],r["board"],r["id"]]
            assert r["day7"]==int(prev["y"])
            if r["oracle_linked"]:
                assert int(r["oracle_active_count"]>0)==int(prev["x"])
            assert int(bool(r["asof_active_count"]))==int(prev["x_title_asof"])
    with (HERE/"history.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows),"entries",len(known_old),"complete labels",Counter(r["exit_observed"] for r in rows))


if __name__=="__main__":
    main()
