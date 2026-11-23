"""Identification bounds for the number of platform series in a selected list."""
from collections import defaultdict
from pathlib import Path
from statistics import mean
import sys

from title_keys import read, write

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "policies"))
from policies import BOARDS, KS, RULES, load_panels, select_orders


def main():
    days, panels = load_panels()
    proxies = {r["id"]: r["group"] for r in read(HERE / "asof_groups.csv")}
    observed = defaultdict(list)
    for day in days:
        for board in BOARDS:
            rows = [dict(r, reference=r["group"], group=proxies[r["id"]]) for r in panels[day, board]]
            order = select_orders(rows)
            for k in KS:
                for policy in RULES:
                    slate = order[policy][:k]
                    known = {r["reference"] for r in slate if r["reference"].startswith("g:")}
                    unknown = sum(r["reference"].startswith("i:") for r in slate)
                    # All unknowns can attach to a known group, or each can form its own.
                    lower = max(1, len(known))
                    upper = len(known) + unknown
                    assert 1 <= lower <= upper <= k
                    observed[board, k, policy].append((lower, upper, unknown))
    records = []
    for (board, k, policy), days_for_rule in observed.items():
        records.append(dict(board=board, k=k, policy=policy, n_days=len(days_for_rule),
                            min_mean_groups=mean(r[0] for r in days_for_rule),
                            max_mean_groups=mean(r[1] for r in days_for_rule),
                            mean_unlinked_slots=mean(r[2] for r in days_for_rule)))
    write(HERE / "coverage_bounds.csv", records)


if __name__ == "__main__":
    main()
