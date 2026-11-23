"""Read a minimal identity projection from public Hongguo detail HTML. No media requests."""
from pathlib import Path
import datetime as dt
import json
import time
from urllib.error import HTTPError
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "official_web_identity.json"
pairs = json.loads((HERE / "independent_candidate_selection.json").read_text())
ids = sorted({x[key] for x in pairs for key in ("pre", "post")})
if SOURCE.exists():
    result = json.loads(SOURCE.read_text())
else:
    result = {"fields_path": "loaderData.detail_page.seriesDetail", "pages": {}, "failures": {}}
# Companion snapshot for operations. The separate identity and synopsis coding inputs omit it.
metric_path = HERE.parent / "prospective" / "detail_favorites_companion.json"
metric_path.parent.mkdir(parents=True, exist_ok=True)
metrics = json.loads(metric_path.read_text()) if metric_path.exists() else {}
for series_id in ids:
    if series_id in result["pages"]:
        continue
    url = "https://hongguoduanju.com/detail?series_id=" + series_id
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        with urlopen(url, timeout=12) as response:
            html = response.read().decode("utf-8")
            http_status = response.status
        data, _ = json.JSONDecoder().raw_decode(html.split("_ROUTER_DATA = ", 1)[1])
        detail = data["loaderData"]["detail_page"]["seriesDetail"]
        record = {key: detail.get(key) for key in ("series_id", "series_name", "first_visible_time", "season_info", "record_number")}
        record.update(url=url, fetched_at_utc=stamp, http_status=http_status)
        if str(record["series_id"]) != series_id:
            raise ValueError("Returned different series ID")
        display = data["loaderData"]["detail_page"].get("seriesSocialInfo", {}).get("series_favorite_count")
        metrics[series_id] = {"public_fav_display": display, "fetched_at_utc": stamp, "url": url}
        metric_temp = metric_path.with_suffix(".partial")
        metric_temp.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
        metric_temp.replace(metric_path)
        result["pages"][series_id] = record
        result["failures"].pop(series_id, None)
    except (HTTPError, OSError, KeyError, IndexError, ValueError) as err:
        result["failures"][series_id] = {"url": url, "at": stamp, "error": str(err)[:150]}
    temporary = SOURCE.with_suffix(".partial")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(SOURCE)
    if series_id in result["failures"] and any(x in result["failures"][series_id]["error"] for x in ("401", "403", "429")):
        break
    time.sleep(1.10)
print(f"{len(result['pages'])} pages retrieved, {len(result['failures'])} failures")
