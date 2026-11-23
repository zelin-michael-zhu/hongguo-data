"""Classify the frozen reservation cohort without assuming unnumbered means first."""
import csv
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDENTITY_PATH = HERE / "cohort_identity_initial.csv"
SNAPSHOT_PATH = HERE / "预约榜_当日快照.json"
PREVIOUS_CATALOG = HERE.parent / "hongguo_free_pilot_2026-11-18/history/catalog.csv"
CLASSIFICATIONS = {"first_work", "sequel", "unknown"}
NUMBER = r"[0-9一二三四五六七八九十百零〇两]+"
TITLE_ORDINAL = re.compile(rf"第({NUMBER})[季期部](?=$|[\W_]|[完终大上中下])")
INTRO_ORDINAL = re.compile(rf"^\s*第({NUMBER})[季期部](?=[\s，,。:：]|$)")
FIRST_NUMBERS = {"1", "01", "一"}

# Each link was checked against the earlier title, format and a distinctive
# character or plot detail appearing in both versions' catalog synopses.
CORROBORATED_PREDECESSORS = {
    "7704896737504136216": ("7704219652255140889", "陈昊宇、恶鬼之牙和龙目城"),
    "7705651789206408216": ("7703760419889876030", "异族围猎、死亡考试"),
    "7707589533084159000": ("7704577081954274328", "黛蜜梨、镇北王萧戡"),
    "7696018525042789438": ("7694896136963755032", "观溪月、宁菲和谢临"),
    "7706462249057012760": ("7705081162988801086", "楚少野"),
    "7709811922383670297": ("7704742001933044760", "余羡、华元都"),
    "7707523680938495001": ("7706056509775449112", "郁圆、方木危和楚栀"),
}
SPINOFF_NOTES = {
    "7703791867338427417": "同名系列衍生作品。简介以万妖派对和院线活动为主，未确认是首部或编号续季。",
}


def classify_title(title, description=""):
    """Return (classification, evidence) from affirmative official wording."""
    title = unicodedata.normalize("NFKC", title)
    description = unicodedata.normalize("NFKC", description or "")
    match = TITLE_ORDINAL.search(title)
    field = "官网预约标题"
    if match is None:
        match = INTRO_ORDINAL.search(description)
        field = "官网预约简介开头"
    if match is None:
        return "unknown", "官网预约信息未明确标明首次或后续季，待核验。"

    ordinal = match[1]
    if ordinal in FIRST_NUMBERS or (ordinal.isdecimal() and int(ordinal) == 1):
        return "first_work", f"{field}明示「{match[0]}」。"
    if ordinal not in {"零", "〇"} and (not ordinal.isdecimal() or int(ordinal) > 1):
        return "sequel", f"{field}明示「{match[0]}」。"
    return "unknown", "官网预约页序号不足以核实首部或续季。"


def read_identity(path=IDENTITY_PATH):
    """Read the reviewed cohort identities by exact string ID."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    by_id = {}
    for row in records:
        series_id = row["series_id"]
        if (not series_id.isdecimal() or series_id in by_id or row["classification"] not in CLASSIFICATIONS
                or not row["classification_evidence"].strip()):
            raise ValueError(f"Invalid or duplicated reservation identity: {series_id}")
        by_id[series_id] = row
    return by_id


def build_initial():
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rows = payload["rows"]
    ids = [str(row["seriesId"]) for row in rows]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("The frozen reservation snapshot must contain 100 distinct series IDs")
    with PREVIOUS_CATALOG.open(encoding="utf-8-sig", newline="") as handle:
        catalog = {row["id"]: row for row in csv.DictReader(handle)}
    evidence_rows = []
    for row in rows:
        series_id = str(row["seriesId"])
        title = row["title"]
        classification, evidence = classify_title(title, row.get("description", ""))
        related_id = ""
        if series_id in CORROBORATED_PREDECESSORS:
            related_id, anchors = CORROBORATED_PREDECESSORS[series_id]
            predecessor = catalog[related_id]
            classification = "sequel"
            evidence = f"预约标题的续作序号与此前《{predecessor['title']}》相接，两者同类型且简介线索一致（{anchors}）。"
        if series_id in SPINOFF_NOTES:
            evidence = SPINOFF_NOTES[series_id]
        evidence_rows.append({
            "series_id": series_id,
            "title": title,
            "format": next(iter(row.get("tags") or []), ""),
            "reservation_rank": row["rank"],
            "classification": classification,
            "classification_evidence": evidence,
            "reservation_source": row["source_url"],
            "related_series_id": related_id,
            "related_source": f"https://hongguoduanju.com/detail?series_id={related_id}" if related_id else "",
        })
    return evidence_rows


if __name__ == "__main__":
    records = build_initial()
    with IDENTITY_PATH.open("x", encoding="utf-8-sig", newline="") as result:
        writer = csv.DictWriter(result, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
