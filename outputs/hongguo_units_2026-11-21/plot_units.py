"""Draw a chart of observed titles and bounded distinct series for the two focus charts."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
from matplotlib import pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    with (HERE / "concentration/concentration_summary.csv").open(encoding="utf-8-sig") as f:
        rows = {(r["board"], r["scenario"]): r for r in csv.DictReader(f)
                if r["period"] == "all39" and r["depth"] == "100"}
    for font in ("Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", "SimHei"):
        if font in font_manager.get_font_names():
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    fig.subplots_adjust(left=.14, right=.95, top=.76, bottom=.28)
    navy, teal = "#1e3a54", "#008371"
    ax.set_xlim(160, 700)
    ax.set_ylim(-.65, 1.55)
    ax.set_yticks([1, 0], ["AI 剧榜", "漫剧榜"], fontsize=13)
    ax.set_xticks(range(200, 701, 100))
    ax.tick_params(axis="both", length=0, pad=7, colors=navy)
    ax.grid(axis="x", color="#dfe6ec")
    for side in ax.spines.values():
        side.set_visible(False)
    for y, code in ((1, "ai"), (0, "comic")):
        all_entities = rows[code, "all_with_singleton_unknown"]
        known = rows[code, "known_only"]
        lower = int(known["pooled_distinct_groups"])
        upper = int(all_entities["pooled_distinct_groups"])
        titles = int(all_entities["pooled_distinct_titles"])
        ax.plot([lower, upper], [y, y], color=teal, linewidth=6, solid_capstyle="round", zorder=3)
        ax.scatter([lower, upper], [y, y], edgecolors=teal, facecolors="white", s=55, zorder=4)
        for value in (lower, upper):
            ax.text(value, y+.24, str(value), ha="center", color=teal, fontsize=12)
        ax.scatter(titles, y, color=navy, s=67, zorder=4)
        ax.text(titles, y+.24, str(titles), ha="center", color=navy, fontsize=12)
    fig.text(.06, .91, "漫剧榜出现过更多作品，独立系列数的可能范围却有重叠", fontsize=17, color=navy)
    fig.text(.06, .79, "39 个完整日  ·  每日同榜前 100 名  ·  跨日去重", fontsize=11, color="#536879")
    fig.text(.13, .13, "绿线  系列数可能范围（下限为已核系列，上限将每个未知作品单列）", fontsize=10, color=teal)
    fig.text(.13, .052, "深色圆点  不同作品 ID 数。范围取决于缺失身份如何归组。", fontsize=10, color=navy)
    fig.savefig(HERE / "作品数与系列数.png", dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
