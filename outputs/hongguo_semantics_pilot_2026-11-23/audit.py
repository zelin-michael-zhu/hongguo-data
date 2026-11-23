"""Check what the saved, dated public previews can measure before modeling."""
import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DAYS = ("2026-11-21", "2026-11-22")
UTC8 = ZoneInfo("Asia/Shanghai")
PILOT = OUT / "hongguo_sentiment_pilot_2026-11-21"
DAILY = OUT / "hongguo_ai_chase_2026-11-22" / "daily"
EXPANSION = OUT / "hongguo_expansion_2026-11-21"

RULES = {
    "stop_or_fast_forward_wording": r"弃[剧坑]|不追了|追不动了|看不下去|劝退|退出观看|快进了",
    "slow_pace_wording": r"拖沓|拖拉|太拖|节奏.{0,4}慢|水剧情|灌水|凑时长|剧情.{0,4}啰嗦",
    "weak_ending_wording": r"烂尾|结尾太|虎头蛇尾|高开低走",
    "visual_audio_mention": r"配音|音色|声音|声线|建模|画风|穿帮|口型",
    "continuation_wording": r"下一[季集]|出第.{0,4}季|快更新|等更新|催更|坐等|什么时候更新|追到第",
}


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_pages(day):
    rows = (json.loads(path.read_text(encoding="utf-8"))
            for path in (PILOT / "snapshots" / day).glob("*.json"))
    return {(row["series_id"], row["scope"]): row for row in rows}


def keys(page):
    return {(int(row["comment_time"]), unicodedata.normalize("NFKC", row["text"]).strip()): row["position"]
            for row in page["rows"]}


def compare_pages(past, later):
    compared = []
    for sid, scope in sorted(past.keys() & later.keys()):
        first, second = past[sid, scope], later[sid, scope]
        old, new = keys(first), keys(second)
        assert len(old) == len(first["rows"]) and len(new) == len(second["rows"])
        cutoff = datetime.fromisoformat(first["sampled_at_sh"]).timestamp()
        first_seen = new.keys() - old.keys()
        compared.append({
            "title": second["title"], "series_id": sid, "scope": scope,
            "prior_at": first["sampled_at_sh"], "later_at": second["sampled_at_sh"],
            "prior_rows": len(old), "later_rows": len(new), "retained": len(old.keys() & new.keys()),
            "changed_positions": sum(old[k] != new[k] for k in old.keys() & new.keys()),
            "newly_visible": len(first_seen),
            "newly_visible_but_previously_published": sum(key[0] < cutoff for key in first_seen),
        })
    return compared


def check_candidates(day, pages):
    eligible = [r for r in table(DAILY / day / "cohort.csv") if r["forecast_eligible"] == "1"]
    texts = [(row["series_id"], scope, review)
             for row in eligible
             for scope in ("series_review", "first_episode_comment")
             for review in pages[row["series_id"], scope]["rows"] if review["text"].strip()]
    matches = {}
    for label, expression in RULES.items():
        hits = [(sid, review) for sid, _, review in texts if re.search(expression, review["text"])]
        matches[label] = {"text_rows": len(hits), "titles": len({sid for sid, _ in hits})}
    start_dates = {r["series_id"]: r["same_board_first_observed"] for r in eligible}
    recent = Counter(scope for sid, scope, review in texts
                     if datetime.fromtimestamp(int(review["comment_time"]), UTC8).date().isoformat() >= start_dates[sid])
    result = {
        "forecast_title_days": len(eligible), "nonblank_text_rows": len(texts),
        "texts_by_scope": Counter(scope for _, scope, _ in texts), "published_since_observed_entry": recent,
        "keyword_candidates": matches, "mature_labels_present": (DAILY / day / "labels_7d.csv").exists(),
    }
    return result, set(start_dates)


def main():
    pages = [load_pages(day) for day in DAYS]
    repeat = compare_pages(*pages)
    cohort = [check_candidates(day, page) for day, page in zip(DAYS, pages)]
    corpus = table(EXPANSION / "reviews_preview.csv")
    all_previews = [row for page in pages for snapshot in page.values() for row in snapshot["rows"]]
    result = {
        "days": DAYS, "corpus": {
            "titles": len({row["series_id"] for row in corpus}),
            "text_rows": len(corpus), "stable_comment_ids": sum(bool(row["source_comment_id"]) for row in corpus),
        },
        "daily_snapshot_rows": len(all_previews),
        "daily_rows_with_integer_publication_time": sum(str(row["comment_time"]).isdecimal() for row in all_previews),
        "daily_rows_with_stable_id": sum(bool(row["comment_id"]) for row in all_previews),
        "repeat_titles": len({row["series_id"] for row in repeat}), "repeat_pages": len(repeat),
        "repeat_newly_visible": sum(r["newly_visible"] for r in repeat),
        "repeat_newly_visible_already_published": sum(r["newly_visible_but_previously_published"] for r in repeat),
        "forecast_unique_titles": len(cohort[0][1] | cohort[1][1]),
        "forecast_dates": {day: numbers for day, (numbers, _) in zip(DAYS, cohort)},
        "repeat_page_details": repeat,
    }
    path = HERE / "公开评论快照核验.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
