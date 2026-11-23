"""Archive the reservation board and follow the frozen 100 titles through D0 and D7."""
import argparse
import csv
import fcntl
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.error import HTTPError

from classify import classify_title, read_identity
from compare_signals import compare
from probe import HERE, SHANGHAI, normalized, now, number, rank_chart, status

TRACKING = HERE / "tracking"
SEED_DATE = "2026-11-22"
ACCESS_LIMIT = {401, 403, 429}
ENDPOINT_TOLERANCE = timedelta(hours=1)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_rows(path, rows):
    temporary = path.with_suffix(".part")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def stamp(text):
    return datetime.fromisoformat(text).astimezone(SHANGHAI)


def seed():
    chart = load(HERE / "预约榜_当日快照.json")
    cohort = {str(row["seriesId"]): row for row in chart["rows"]}
    identity = read_identity()
    if len(cohort) != 100 or cohort.keys() != identity.keys():
        raise ValueError("Frozen reservation cohort and identity audit differ")
    reviews_path = HERE / "cohort_identity_updates.csv"
    if reviews_path.exists():
        for sid, correction in read_identity(reviews_path).items():
            if sid not in identity or not (correction.get("source_url") or "").startswith("https://"):
                raise ValueError(f"Classification update needs a cohort ID and an evidence URL: {sid}")
            identity[sid].update(classification=correction["classification"],
                                 classification_evidence=correction["classification_evidence"] + " " + correction["source_url"],
                                 exclude_main_comparison=correction.get("exclude_main_comparison") == "1")
    base = TRACKING / SEED_DATE
    if not (base / "reservation.json").exists():
        write(base / "reservation.json", chart)
    for row in load(HERE / "官方正片核查.json"):
        sid = row["series_id"]
        path = base / "players" / f"{sid}.json"
        if sid in cohort and not path.exists():
            write(path, dict(row, cohort_id=sid, match_method="same_id"))
    return cohort, identity


def charts_and_players():
    signals, checks = defaultdict(list), defaultdict(list)
    for folder in sorted(TRACKING.glob("????-??-??")):
        path = folder / "reservation.json"
        if path.exists():
            for row in load(path)["rows"]:
                if row["reservationOnly"] and row["episodeCount"] == 0:
                    signals[str(row["seriesId"])].append(row)
        for path in folder.glob("players/*.json"):
            row = load(path)
            if stamp(row["sampled_at_sh"]).date().isoformat() != folder.name:
                raise ValueError(f"Date mismatch in {path}")
            checks[row.get("cohort_id") or path.stem].append(row)
    return signals, checks


def first_public(checks):
    return next((row for row in checks if row["status"] == "public_first_episode"), None)


def launch_window(checks, public):
    """Use a corroborated website date, or a transition observed within one day."""
    observed = stamp(public["sampled_at_sh"])
    negative = [stamp(row["sampled_at_sh"]) for row in checks
                if row["http_status"] == 404 and row["series_id"] == public["series_id"]
                and stamp(row["sampled_at_sh"]) < observed]
    prior = max(negative, default=None)
    metadata = public["first_visible_at_metadata"]
    if prior and prior.date() == observed.date():
        return observed.date(), prior, "same_day_transition"
    if metadata:
        visible = stamp(metadata)
        if visible <= observed and visible.date() == observed.date() and (not prior or prior <= visible):
            return observed.date(), visible, "same_day_website_metadata"
        if prior and prior <= visible < observed and visible.date() < observed.date():
            return visible.date(), visible, "older_website_metadata"
    return None, None, "launch_day_unverified_or_missed"


def endpoints(checks, public, day, today):
    if day is None:
        return None, None, "", "launch_day_unverified_or_missed"
    due = day + timedelta(days=7)
    usable = [row for row in checks if row["status"] == "public_first_episode"
              and row["series_id"] == public["series_id"] and row["source_url"] == public["source_url"]
              and str(row["favorite_count"]).isdecimal()]
    d0 = next((row for row in usable if stamp(row["sampled_at_sh"]).date() == day), None)
    by_day7 = [row for row in usable if stamp(row["sampled_at_sh"]).date() == due]
    d7 = by_day7[0] if by_day7 else None
    if d0 and d7 and abs(stamp(d7["sampled_at_sh"]) - stamp(d0["sampled_at_sh"]) - timedelta(days=7)) > ENDPOINT_TOLERANCE:
        return d0, d7, due.isoformat(), "endpoint_times_differ"
    label = "missing_d0" if d0 is None else "complete" if d7 else "waiting_d7" if due >= today else "missing_d7"
    return d0, d7, due.isoformat(), label


def evaluate(cohort, identity, signals, checks, today):
    rows = []
    for sid, item in cohort.items():
        records = sorted(checks[sid], key=lambda row: stamp(row["sampled_at_sh"]))
        public = first_public(records)
        group = identity[sid]["classification"]
        group_evidence = identity[sid]["classification_evidence"]
        if public and group == "unknown" and not identity[sid].get("exclude_main_comparison"):
            inferred, evidence = classify_title(public["title"], public.get("description", ""))
            if inferred != "unknown":
                group, group_evidence = inferred, evidence
        day, bound, method = launch_window(records, public) if public else (None, None, "")
        final = (endpoints(records, public, day, today) if public else (None, None, "", "waiting_for_release"))
        d0, d7, due, stage = final
        eligible = [r for r in signals[sid] if bound and stamp(r["sampled_at_sh"]) < bound
                    and number(r["subscribeText"], "人预约") is not None
                    and number(r["primaryMetricText"], "期待") is not None]
        pre = max(eligible, key=lambda r: stamp(r["sampled_at_sh"]), default=None)
        gain = int(d7["favorite_count"]) - int(d0["favorite_count"]) if stage == "complete" else ""
        latest = records[-1] if records else {}
        rows.append({
            "series_id": sid, "title": item["title"], "format": identity[sid]["format"],
            "classification": group, "classification_evidence": group_evidence,
            "exclude_main_comparison": bool(identity[sid].get("exclude_main_comparison")),
            "pre_observed_at": pre["sampled_at_sh"] if pre else "",
            "pre_reservations": number(pre["subscribeText"], "人预约") if pre else "",
            "pre_expectation": number(pre["primaryMetricText"], "期待") if pre else "",
            "frozen_pre_observed_at": item["sampled_at_sh"],
            "first_post_date": stamp(public["sampled_at_sh"]).date().isoformat() if public else "",
            "site_first_visible_at": public["first_visible_at_metadata"] if public else "",
            "launch_date": day.isoformat() if day else "", "launch_evidence": method, "day7_due": due,
            "day0_favorite": d0["favorite_count"] if d0 else "", "day7_favorite": d7["favorite_count"] if d7 else "",
            "day0_at": d0["sampled_at_sh"] if d0 else "", "day7_at": d7["sampled_at_sh"] if d7 else "",
            "source": public["source_url"] if public else "", "week_gain": gain,
            "matched_series_id": public["series_id"] if public else "",
            "match_method": public["match_method"] if public else "",
            "site_season_group_id": public.get("site_season_group_id", "") if public else "",
            "capture_status": stage, "last_player_status": latest.get("status", ""),
            "last_checked_at": latest.get("sampled_at_sh", ""),
        })
    return rows


def archive(folder, slug, filename):
    path = folder / filename
    if path.exists():
        return load(path), None
    try:
        chart = rank_chart(slug)
        if any(stamp(page["sampled_at_sh"]).date().isoformat() != folder.name for page in chart["pages"]):
            raise ValueError("Chart fetch crossed the Shanghai date boundary")
        write(path, chart)
        return chart, None
    except (OSError, ValueError, KeyError) as exc:
        return None, {"source": slug, "checked_at": now(), "error": str(exc),
                      "http_status": exc.code if isinstance(exc, HTTPError) else None}


def alias(item, new, fixed_ids):
    match = [row for row in new if normalized(row["title"]) == normalized(item["title"])
             and row["tags"] and item["tags"] and row["tags"][0] == item["tags"][0]
             and not row["reservationOnly"] and row["episodeCount"] > 0]
    if len(match) != 1:
        return ""
    target = match[0]
    intro, other = normalized(item["description"]), normalized(target["description"])
    candidate = str(target["seriesId"])
    if candidate not in fixed_ids and len(intro) >= 55 and other.startswith(intro[:55]):
        return candidate
    return ""


def capture(today, cohort, state):
    folder = TRACKING / today.isoformat()
    receipt = folder / "run_issues.json"
    if receipt.exists() and any(issue["http_status"] in ACCESS_LIMIT for issue in load(receipt)):
        return
    _, error = archive(folder, "subscribe-drama", "reservation.json")
    errors = [error] if error else []
    restricted = bool(error and error["http_status"] in ACCESS_LIMIT)
    new = None
    if not restricted and any(not row["first_post_date"] for row in state):
        new, error = archive(folder, "new-drama", "new.json")
        if error:
            errors.append(error)
            restricted = error["http_status"] in ACCESS_LIMIT
    new_items = new["rows"] if new else []
    alternatives = {sid: alias(item, new_items, cohort) for sid, item in cohort.items()}
    aliases_found = Counter(alternatives.values())
    _, observed = charts_and_players()
    for record in state:
        if restricted or stamp(now()).date() != today:
            break
        sid = record["series_id"]
        if record["first_post_date"] and today.isoformat() not in (record["launch_date"], record["day7_due"]):
            continue
        alternate = alternatives[sid]
        targets = [record["matched_series_id"] or sid]
        if alternate and aliases_found[alternate] == 1 and not record["matched_series_id"]:
            targets.append(alternate)
        for target in targets:
            saved = {row["series_id"]: row for row in sorted(observed[sid], key=lambda row: row["sampled_at_sh"])
                     if stamp(row["sampled_at_sh"]).date() == today}
            old = saved.get(target, {})
            if old.get("status") == "public_first_episode" and str(old.get("favorite_count")).isdecimal():
                break
            if old.get("http_status") == 404:
                continue
            row = status(target)
            at = stamp(row["sampled_at_sh"])
            if at.date() != today:
                break
            method = "same_id" if target == sid else "title_synopsis_format"
            path = folder / "players" / f"{sid}_{target}_{at:%H%M%S}.json"
            write(path, dict(row, cohort_id=sid, match_method=method))
            if row["http_status"] in ACCESS_LIMIT:
                errors.append({"source": row["source_url"], "checked_at": row["sampled_at_sh"],
                               "error": row["status"], "http_status": row["http_status"]})
                restricted = True
                break
            if row["status"] == "public_first_episode":
                break
    write(receipt, errors)


def publish(today, cohort, identity):
    signals, checks = charts_and_players()
    rows = evaluate(cohort, identity, signals, checks, today)
    write_rows(TRACKING / "首批100部_上线与首周收藏.csv", rows)
    analysis = compare(row for row in rows if row["capture_status"] == "complete" and not row["exclude_main_comparison"])
    day_folder = TRACKING / today.isoformat()
    write(day_folder / "comparison.json", analysis)
    current_players = [row for items in checks.values() for row in items
                       if stamp(row["sampled_at_sh"]).date() == today]
    summary = {
        "date": today.isoformat(), "reservation_pages_complete": (day_folder / "reservation.json").exists(),
        "cohort": len(rows), "verified_post": sum(bool(row["first_post_date"]) for row in rows),
        "by_stage": dict(Counter(row["capture_status"] for row in rows)),
        "classification": dict(Counter(row["classification"] for row in rows)),
        "confirmed_spinoff_excluded": sum(row["exclude_main_comparison"] for row in rows),
        "today_player_checks": dict(Counter(row["status"] for row in current_players)),
        "paired_outcomes_by_group": {key: data["n_complete"] for key, data in analysis["groups"].items()},
        "complete_endpoints_missing_signals": analysis["n_incomplete"],
        "complete_unknown": analysis["n_complete_unclassified"],
    }
    write(day_folder / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="Initialize and recompute from saved observations only")
    args = parser.parse_args()
    today = stamp(now()).date()
    TRACKING.mkdir(exist_ok=True)
    with (TRACKING / ".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cohort, identity = seed()
        if not args.rebuild:
            signals, checks = charts_and_players()
            capture(today, cohort, evaluate(cohort, identity, signals, checks, today))
        publish(today, cohort, identity)


if __name__ == "__main__":
    main()
