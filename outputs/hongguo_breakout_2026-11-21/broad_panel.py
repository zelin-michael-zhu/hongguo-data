"""Create the broader candidate grid for a separate contemporaneous webpage-age filter."""

from panel import observed_charts, make_rows, add_labels, write, read, HERE


def main():
    charts, boards = observed_charts()
    # No dashboard-age upper cut: this lets us identify cases where the recorded webpage
    # date postdates a title's first chart observation, rather than silently deleting them.
    rows = make_rows(charts, boards, min_age=1, max_age=len(charts))
    add_labels(rows, charts, boards)
    rows.sort(key=lambda r:(r["date"],r["rank"],r["id"]))
    write("broad_panel.csv", rows)
    source = read(HERE / "panel.csv")
    check = [r for r in read(HERE / "broad_panel.csv") if 3<=int(r["age"])<=7]
    assert check==source
    print(len(rows), len(check), "prior chart rows reproduced")


if __name__=="__main__":
    main()
