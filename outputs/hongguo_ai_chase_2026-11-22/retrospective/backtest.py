"""Run a historical simulation from the November 21 surviving public review cards."""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import re
import sys
import unicodedata
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from freeze_board_only import fit_scores
from run import OUTPUTS, PILOT, read, observed_charts
from compare_nov28 import csv_bytes, percentiles, WEIGHT

ZONE = ZoneInfo("Asia/Shanghai")
ARCHIVE = OUTPUTS / "hongguo_expansion_2026-11-21/reviews_preview.csv"
SOURCES = OUTPUTS / "hongguo_franchise_forecast_2026-11-21/own_source_checks.csv"
LABELS = PILOT / "same_board_historical_labeled.csv"

POSITIVE = re.compile(
    r"好看|挺不错|很不错|都不错|太棒了|真棒|演得好|演技.{0,3}(?:好|棒|不错|在线)|"
    r"剧情.{0,4}(?:不错|好|有意思|紧凑|精彩)|制作.{0,4}(?:精良|用心|精致)|"
    r"画[面质].{0,4}(?:好|美|精致)|喜欢这[部剧]|喜欢[这该]剧|精彩|值得(?:一看|看)|"
    r"推荐(?:观看|去看|给大家|大家看)|良心[短好]?剧|(?:爽|甜|过瘾)剧|好剧|"
    r"拍得(?:真好|不错|好|可以)|剧本.{0,3}(?:好|不错)|打戏.{0,3}(?:好|精彩)|"
    r"爱看|有新意|上头"
)
CHASE = re.compile(
    r"(?:想|要|愿意|坐等|继续|接着|期待|等不及).{0,5}(?:追|看下去|看后续|看后面|看续集|看下一[季部集]|看第[二三四五六七八九十\d]+[季部集])|"
    r"追下去|追定了|一追到底|没看够|不够看|不过瘾|催更|坐等更新|"
    r"(?:求|盼|期待|坐等|想看|等不及|我要看).{0,8}(?:更新|爆更|更完|续[集作]|后续|下[一]?季|下一集|下一部|第[二三四五六七八九十\d]+[季部集])|"
    r"(?:赶紧|快点|加油|记得|给我|速度|求求|快快|继续).{0,6}(?:更[新完]|[出拍]续集|出.{0,3}[下二三四五六七八九十][一二三四五六七八九十]?[季部集])|"
    r"快更|求更|求第[二三四五六七八九十\d]+季|"
    r"(?:后续|下季|下一季|第二季|第三季|第四季|第五季|续集).{0,7}(?:快出|快更|催更|期待|给我.{0,3}速度)"
)
NEGATION = re.compile(r"(?:不怎么|不觉得|别说|没有|觉得不|没觉得|不好|别|哪[里儿]|何来|不太|并不|不是很|不|没|并非|不想|不愿意|懒得|不会再|谁会)[^，。！？；,!?;]{0,2}$")
PROMO = re.compile(
    r"我在[本这]剧.{0,7}(?:出演|饰演|扮演|担任)|我饰演的|我扮演的|"
    r"(?:我是|我们是)(?:[本这]剧的?)?(?:主创|导演|编剧|制作人|演员|制片)|"
    r"(?:我们|本团队).{0,7}(?:拍摄|制作|出品).{0,12}(?:感谢|上线|大家支持)|"
    r"我们(?:这部剧|剧组|制作组|团队).{0,15}(?:发布|开拍|上映|上线|制作)|"
    r"作为[本这]剧(?:的)?(?:导演|编剧|制片|演员)"
)


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def positive_match(pattern, text):
    return any(not NEGATION.search(text[max(0, m.start()-8):m.start()]) for m in pattern.finditer(text))


def classify(text):
    return dict(quality_positive=int(positive_match(POSITIVE, text)),
                chase_intent=int(positive_match(CHASE, text)),
                self_declared_promo=int(bool(PROMO.search(text))))


def read_reviews(ids):
    result = defaultdict(list)
    all_keys = set()
    for row in read(ARCHIVE):
        sid = row["series_id"]
        if sid not in ids or row["scope"] != "series_review":
            continue
        text = normalize(row["text"])
        if not text:
            continue
        published = datetime.fromtimestamp(int(row["create_time_raw"]), ZONE)
        captured = datetime.fromisoformat(row["collected_at_utc"]).astimezone(ZONE)
        assert published <= captured and captured.date() == date(2026, 11, 21)
        key = (sid, published, text)
        if key in all_keys:
            continue
        all_keys.add(key)
        result[sid].append(dict(series_id=sid, display_position=row["display_position"],
                                published_at=published, **classify(text)))
    return result


def write(name, rows):
    (HERE / name).write_bytes(csv_bytes(rows))


def review_signals(title_reviews, cutoff, n_min):
    known = [r for r in title_reviews if r["published_at"] <= cutoff and not r["self_declared_promo"]]
    n = len(known)
    positive = sum(r["quality_positive"] for r in known)
    chase = sum(r["chase_intent"] for r in known)
    return (n, positive / n, chase / n) if n >= n_min else (n, "", "")


def apply_semantic_labels(reviews, historical, exact, held_out):
    last_cutoff = {}
    for row in historical:
        ds, sid = row["date"], row["series_id"]
        if (ds, sid) in held_out:
            last_cutoff[sid] = max(last_cutoff.get(sid, exact[ds]), exact[ds])
    selected = {(r["series_id"], r["display_position"]): r
                for sid, cutoff in last_cutoff.items() for r in reviews[sid] if r["published_at"] <= cutoff}
    paths = [HERE / filename for filename in ("heldout_labels_a.csv", "heldout_labels_b.csv")]
    if not all(path.exists() for path in paths):
        return reviews, 0
    codes = [r for path in paths for r in read(path)]
    labels = {(r["series_id"], r["display_position"]): r for r in codes}
    assert len(labels) == len(codes) and selected.keys() == labels.keys()
    updated = defaultdict(list)
    for (sid, pos), row in selected.items():
        values = {field: int(labels[sid, pos][field])
                  for field in ("quality_positive", "chase_intent", "self_declared_promo")}
        assert set(values.values()) <= {0, 1}
        updated[sid].append({**row, **values})
    return updated, len(labels)


def ranks(group, column):
    order = sorted(group, key=lambda r: (-r[column], -r["board_score"], int(r["rank"]), r["series_id"]))
    return {r["series_id"]: i for i, r in enumerate(order, 1)}


def rollout(name, rows, reviews, times, n_min, day_scores):
    daily = defaultdict(list)
    for row in rows:
        ds, sid = row["date"], row["series_id"]
        if (ds, sid) not in day_scores:
            continue
        cutoff = times[ds]
        n, positive, chase = review_signals(reviews.get(sid, []), cutoff, n_min)
        daily[ds].append(dict(**row, cutoff_sh=cutoff.isoformat(), n_pre_cutoff=n, quality_share=positive,
                              chase_share=chase, board_score=day_scores[ds, sid]))
    details, daily_comparison = [], []
    for ds, group in sorted(daily.items()):
        by_id = {r["series_id"]: r for r in group}
        p_board = percentiles(by_id, "board_score")
        observed = {sid: r for sid, r in by_id.items() if r["quality_share"] != ""}
        p_quality = percentiles(observed, "quality_share") if len(observed) > 1 else {}
        p_chase = percentiles(observed, "chase_share") if len(observed) > 1 else {}
        for sid, row in by_id.items():
            row["quality_score"] = p_board[sid] + WEIGHT * (p_quality.get(sid, .5) - .5)
            row["chase_score"] = row["quality_score"] + WEIGHT * (p_chase.get(sid, .5) - .5)
        for score in ("board", "quality", "chase"):
            placements = ranks(group, f"{score}_score")
            for sid, row in by_id.items():
                row[f"position_{score}"] = placements[sid]
        details.extend(group)
        for k in (5, 10):
            record = dict(setting=name, date=ds, budget=k, slots=min(k, len(group)),
                          candidates=len(group), with_text=len(observed),
                          positives=sum(int(r["future_same_board_top20"]) for r in group))
            for model in ("board", "quality", "chase"):
                selected = [r for r in group if r[f"position_{model}"] <= k]
                record[f"{model}_hits"] = sum(int(r["future_same_board_top20"]) for r in selected)
            daily_comparison.append(record)
    return details, daily_comparison


def quality_audit(path, detected):
    if not path.exists():
        return {}
    counts = defaultdict(Counter)
    for row in read(path):
        key = row["series_id"], row["display_position"]
        for field in ("quality_positive", "chase_intent"):
            counts[field][int(row[field]), detected[key][field]] += 1
    return {field: dict(true_positive=c[1, 1], true_negative=c[0, 0],
                        false_negative=c[1, 0], false_positive=c[0, 1]) for field, c in counts.items()}


def main():
    chart, _ = observed_charts()
    historical = [r for r in read(LABELS) if r["board"] == "ai"]
    assert len(historical) == len({(r["date"], r["series_id"]) for r in historical}) == 424
    reviews = read_reviews({r["series_id"] for r in historical})
    origin_dates = {r["date"] for r in historical}
    exact = {r["date"]: datetime.fromisoformat(r["fetched_at"]).astimezone(ZONE)
             for r in read(SOURCES) if r["date"] in origin_dates}
    midnight = {ds: datetime.combine(date.fromisoformat(ds), time.min, ZONE) for ds in origin_dates}
    assert origin_dates == exact.keys() and all(ds == t.date().isoformat() for ds,t in exact.items())
    eligible = {r["date"] for r in read(HERE.parent / "历史数值基准逐日回测.csv")}
    held_out = {}
    for ds in sorted(eligible):
        day = date.fromisoformat(ds)
        fit = [r for r in historical if date.fromisoformat(r["date"]) + timedelta(days=7) < day]
        test = [r for r in historical if r["date"] == ds]
        assert not ({r["series_id"] for r in fit} & {r["series_id"] for r in test})
        held_out.update({(ds, row["series_id"]): float(score)
                         for row, score in zip(test, fit_scores(chart, fit, test))})
    rank_scores = {(r["date"],r["series_id"]): -int(r["rank"]) for r in historical}
    coded, coded_count = apply_semantic_labels(reviews, historical, exact, held_out)
    plans = (("主回测_原榜采集时点", exact, 1, held_out, coded),
             ("提前截断_当日零点", midnight, 1, held_out, coded),
             ("至少三条_原榜采集时点", exact, 3, held_out, coded),
             ("只匹配明确字词", exact, 1, held_out, reviews),
             ("全部日期_当天名次及词典", exact, 1, rank_scores, reviews))
    daily, totals = [], []
    for i, (name, cut, n_min, scores, text_source) in enumerate(plans):
        details, comparison = rollout(name, historical, text_source, cut, n_min, scores)
        if i == 0:
            write("主回测逐剧.csv", details)
            swaps = [
                dict(date=r["date"], series_id=r["series_id"], title=r["title"], rank=r["rank"],
                     with_positive=int(int(r["position_quality"]) <= 5),
                     with_chase=int(int(r["position_chase"]) <= 5),
                     chase_share=r["chase_share"], total_visible=r["n_pre_cutoff"],
                     future_same_board_top20=r["future_same_board_top20"])
                for r in details if (r["position_quality"] <= 5) != (r["position_chase"] <= 5)
            ]
            if swaps:
                write("追更改变的前五选择.csv", swaps)
        daily.extend(comparison)
        for k in (5, 10):
            selected = [r for r in comparison if r["budget"] == k]
            unique_hits = {
                f"{model}_unique_hit_titles": len({r["series_id"] for r in details
                                                   if r[f"position_{model}"] <= k
                                                   and r["future_same_board_top20"] == "1"})
                for model in ("board", "quality", "chase")
            }
            totals.append(dict(setting=name, coding="semantic" if coded_count and i<3 else "keywords",
                               budget=k, dates=len(selected),
                               titles=len({r["series_id"] for r in details}),
                               candidates=len(details), with_text=sum(r["with_text"] for r in selected),
                               **{key: sum(r[key] for r in selected) for key in
                                  ("slots", "board_hits", "quality_hits", "chase_hits")}, **unique_hits))
    write("回测按日.csv", daily)
    write("回测汇总.csv", totals)
    coverage = {"historical_rows": len(historical),
                "historical_titles": len({r["series_id"] for r in historical}),
                "semantic_coded_distinct_reviews": coded_count,
                "raw_coverage_exact_cutoff": sum(any(x["published_at"] <= exact[r["date"]]
                                                     for x in reviews.get(r["series_id"], [])) for r in historical),
                "keyword_vs_blind_coding": quality_audit(HERE / "qa_labels.csv",
                                                        {(r["series_id"], r["display_position"]): r
                                                         for group in reviews.values() for r in group})}
    (HERE / "核验.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"results": totals, "coverage": coverage}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
