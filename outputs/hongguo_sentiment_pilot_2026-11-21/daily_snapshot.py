"""Freeze same-board candidates, then collect dated public previews, or label an earlier cohort."""
import argparse
import csv
import fcntl
import io
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from capture_previews import collect
from cohort import LOCAL, RAW, observed_charts
from rank_baseline import TIE, distinct_priorities, replay

HERE = Path(__file__).resolve().parent
DAILY = HERE / "daily"
FIELDS = ("priority", "date", "board", "series_id", "title", "rank", "same_board_age",
          "rank_lag2", "rank_lag1", "heat", "chart_snapshot_completed_sh",
          "forecast_start", "forecast_end", "future_same_board_top20")


def freeze(path, data):
    """Install once without replacing an existing snapshot, including after an interrupted write."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Existing snapshot differs: {path}")
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def csv_bytes(rows, fields):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def verified_chart(folder, day):
    manifest = json.loads((folder / "manifest.json").read_text())
    boards, times = {}, []
    if set(manifest["boards"]) != set(TIE):
        raise ValueError("Expected hot, real, ai and comic")
    for board in TIE:
        meta = manifest["boards"][board]
        if not meta["fresh_complete"] or meta["errors"] or not meta["pages"]:
            raise ValueError(f"Incomplete {board} chart")
        for page in meta["pages"]:
            stamp = datetime.fromisoformat(page["at"])
            if stamp.tzinfo is None or stamp.astimezone(LOCAL).date() != day or page["label_date"] != day.isoformat():
                raise ValueError(f"Chart not observed and labeled on {day}: {board}")
            times.append(stamp)
        records = json.loads((folder / f"{board}.json").read_text())
        if (len(records) != 100 or {int(r["rank"]) for r in records} != set(range(1,101))
                or len({str(r["id"]) for r in records}) != 100):
            raise ValueError(f"Invalid ranks or duplicate title ID: {board}")
        boards[board] = records
    return {"date": day.isoformat(), "completed_at": max(times).astimezone(LOCAL).isoformat(),
            "manifest": manifest, "boards": boards}


def ensure_chart(day, folder, args):
    archive = folder / "charts.json"
    if archive.exists() and not args.chart_dir:
        return json.loads(archive.read_text())
    source = args.chart_dir
    if not source and day == date(2026,11,21):
        source = RAW
    if not source:
        if args.offline or day != datetime.now(LOCAL).date() or not args.radar_checkout:
            raise ValueError("Supply --chart-dir pointing to this day's saved chart, or --radar-checkout to fetch today's chart")
        runner = RAW.parent / "capture.py"
        result = subprocess.run([sys.executable, str(runner), str(args.radar_checkout)], check=True,
                                text=True, stdout=subprocess.PIPE)
        names = re.findall(r"^(\d{8}T\d{6})\s", result.stdout, re.MULTILINE)
        if len(names) != 1:
            raise ValueError("Cannot identify archived chart directory from capture.py output")
        source = RAW.parent / names[0]
    payload = verified_chart(source, day)
    freeze(archive, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())
    return payload


def history(through):
    charts, coverage = observed_charts()
    charts = {d: v for d,v in charts.items() if d<=through}
    coverage = {d: v for d,v in coverage.items() if d<=through}
    for path in sorted(DAILY.glob("????-??-??/charts.json")):
        d = date.fromisoformat(path.parent.name)
        if d>through:
            continue
        raw = json.loads(path.read_text())
        if raw["date"] != d.isoformat():
            raise ValueError(f"Wrong date in {path}")
        titles, board_ranks = defaultdict(dict), defaultdict(set)
        for b, records in raw["boards"].items():
            for r in records:
                sid, rank = str(r["id"]), int(r["rank"])
                titles[sid][b] = dict(title=r["title"], rank=rank, heat=r.get("heat"))
                board_ranks[b].add(rank)
        if d in charts:
            existing = {(sid,b,r["rank"]) for sid,ent in charts[d].items() for b,r in ent.items()}
            current = {(sid,b,r["rank"]) for sid,ent in titles.items() for b,r in ent.items()}
            if existing != current:
                raise ValueError(f"Archive sources conflict on {d}")
        charts[d], coverage[d] = titles, board_ranks
    return charts, coverage


def create_cohort(day, folder, args):
    archive = ensure_chart(day, folder, args)
    charts, coverage = history(day)
    # replay verifies a full week on each particular board immediately before
    # the title's first observed appearance. Gaps on unrelated boards do not
    # disqualify a title. Also require coverage between that entry and today.
    pairs = replay(charts, coverage).get(day, [])
    pairs = [r for r in pairs if all(
        coverage.get(day-timedelta(days=k), {}).get(r["board"], set()) == set(range(1,101))
        for k in range(r["same_board_age"]))]
    cohort = distinct_priorities(pairs)
    for row in cohort:
        sid,b = row["series_id"],row["board"]
        lags = [charts.get(day-timedelta(days=k),{}).get(sid,{}).get(b,{}).get("rank","") for k in (2,1)]
        row.update(rank_lag2=lags[0], rank_lag1=lags[1], heat=charts[day][sid][b]["heat"],
                   chart_snapshot_completed_sh=archive["completed_at"], forecast_start=day+timedelta(days=1),
                   forecast_end=day+timedelta(days=7))
        if row["future_same_board_top20"] != "":
            raise ValueError("Future outcome leaked into candidate registry")
    target = folder / "cohort.csv"
    freeze(target, csv_bytes(cohort, FIELDS))
    if day == date(2026,11,21):
        with (HERE / "same_board_m0_frozen.csv").open(encoding="utf-8-sig", newline="") as f:
            old = [(r["series_id"],r["board"],int(r["rank"])) for r in csv.DictReader(f)]
        if old != [(r["series_id"],r["board"],r["rank"]) for r in cohort]:
            raise ValueError("21 November reference cohort changed")
    if cohort and not args.offline:
        collect(target, day.isoformat())
    captured = []
    for row in cohort:
        for scope in ("series_review","first_episode_comment"):
            path = HERE / "snapshots" / day.isoformat() / (row["series_id"]+"_"+scope+".json")
            if path.exists():
                p = json.loads(path.read_text())
                stamp = datetime.fromisoformat(p["sampled_at_sh"])
                if (p["series_id"] != row["series_id"] or p["scope"] != scope or stamp.tzinfo is None
                    or stamp.astimezone(LOCAL).date()!=day or stamp<datetime.fromisoformat(archive["completed_at"])):
                    raise ValueError(f"Invalid dated preview: {path.name}")
                captured.append(stamp)
    print(f"{day}: {len(pairs)} eligible title-board pairs, {len(cohort)} titles; "
          f"{len(captured)}/{len(cohort)*2} verified preview pages; frozen {target}")
    if captured:
        print("Last verified capture:",max(captured).isoformat())
    if len(captured) == len(cohort)*2:
        summary = dict(chart_completed_at=archive["completed_at"], titles=len(cohort),
                       title_board_pairs=len(pairs), verified_pages=len(captured),
                       first_preview_at=min(captured).isoformat() if captured else None,
                       decision_at=max(captured).isoformat() if captured else archive["completed_at"])
        freeze(folder / "batch.json", json.dumps(summary,ensure_ascii=False,indent=2).encode())


def make_labels(day, folder, through):
    if through < day+timedelta(days=7):
        raise ValueError("Seven days have not elapsed; no label was written")
    charts, coverage = history(through)
    with (folder / "cohort.csv").open(encoding="utf-8-sig",newline="") as f:
        cohort = list(csv.DictReader(f))
    rows = []
    for r in cohort:
        result = ""
        for k in range(1,8):
            d = day+timedelta(days=k)
            ranks = coverage.get(d,{}).get(r["board"],set())
            if not set(range(1,21)) <= ranks:
                raise ValueError(f"Missing {r['board']} top 20 on {d}; no label file written")
            rank = charts[d].get(r["series_id"],{}).get(r["board"],{}).get("rank",101)
            if not result and rank<=20:
                result=d.isoformat()
        rows.append(dict(date=r["date"], series_id=r["series_id"], board=r["board"], title=r["title"],
                         first_hit_date=result, future_same_board_top20=int(bool(result))))
    fields = ("date","series_id","board","title","first_hit_date","future_same_board_top20")
    freeze(folder / "labels_7d.csv", csv_bytes(rows,fields))
    print(f"{day}: labeled {len(rows)} titles in {folder / 'labels_7d.csv'}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--day",type=date.fromisoformat,default=datetime.now(LOCAL).date(),
                     help="Shanghai decision date, YYYY-MM-DD")
    src = cli.add_mutually_exclusive_group()
    src.add_argument("--chart-dir",type=Path,help="Existing capture.py archive with manifest.json and four board JSON files")
    src.add_argument("--radar-checkout",type=Path,help="Local drama-radar checkout for capture.py")
    cli.add_argument("--offline",action="store_true",help="Never fetch charts or previews")
    cli.add_argument("--labels-through",type=date.fromisoformat,help="Only label the frozen cohort using charts up to this date")
    args = cli.parse_args()
    folder = DAILY / args.day.isoformat()
    folder.mkdir(parents=True,exist_ok=True)
    with (folder / ".lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.labels_through:
            make_labels(args.day,folder,args.labels_through)
        else:
            create_cohort(args.day,folder,args)
