"""Diagnostics for event definitions, time origin, identities and censoring."""
from collections import Counter
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    with (HERE / name).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def write(name,rows):
    with (HERE / name).open("w",encoding="utf-8-sig",newline="") as f:
        w = csv.DictWriter(f,fieldnames=rows[0])
        w.writeheader()
        w.writerows(rows)


def label(r,mode):
    if r[mode+"_linked"]=="0":
        return "unknown"
    return "linked_active" if int(r[mode+"_active_count"]) else "linked_none_observed"


def resource_check():
    history = read("history.csv")
    own={(r["date"],r["board"],r["id"]):r for r in read("own.csv")}
    events=[r for r in history if r["full_future7"]=="1"]
    counts=[]
    for b in ("all","hot","real","ai","comic"):
        e=[r for r in events if b=="all" or r["board"]==b]
        base=dict(board=b,events=len(e),distinct_titles=len({r["id"] for r in e}),
                  entry_dates=len({r["date"] for r in e}),first=sum(r["entry_type"]=="first_observed" for r in e),
                  reentry=sum(r["entry_type"]=="reentry" for r in e),
                  previous_other_board=sum(int(r["prev_other_board"]) for r in e),
                  new_simultaneous=sum(int(r["simultaneous_new_other"]) for r in e),
                  returned_by_day7=sum(r["day7"]=="1" and int(r["days7"])<7 for r in e))
        for mode in ("asof","oracle"):
            counter=Counter(label(r,mode) for r in e)
            for status in ("unknown","linked_none_observed","linked_active"):
                base[mode+"_"+status]=counter[status]
        own_e=[own[(r["date"],r["board"],r["id"])] for r in e]
        for col in ("heat","likes","favorites","rating"):
            base["present_"+col]=sum(bool(r[col]) for r in own_e)
        counts.append(base)
    write("feature_support.csv",counts)
    # First exit ends a spell, including when the title later re-enters. Administrative censoring at gaps.
    survival=[]
    for status in ("all","unknown","linked_active","linked_none_observed"):
        e=[r for r in history if status=="all" or label(r,"asof")==status]
        probability=1.
        for lag in range(1,15):
            risk=sum(int(r["exit_time"])>=lag for r in e)
            failure=sum(int(r["exit_time"])==lag and r["exit_observed"]=="1" for r in e)
            censored=sum(int(r["exit_time"])==lag and r["exit_observed"]=="0" for r in e)
            if risk==0:
                break
            probability *= 1-failure/risk
            survival.append(dict(status_asof=status,lag=lag,at_risk=risk,first_exit=failure,censored=censored,
                                 probability_no_exit_through_lag=probability))
    write("first_exit_km.csv",survival)


if __name__=="__main__":
    resource_check()
