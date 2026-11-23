"""Exploratory dimension comparisons for the primary outcome, conditional on G."""
from datetime import date, timedelta
from statistics import mean

from forecast import FOLDS, OWN, key, predict, read, write


def main():
    rows = [r for r in read("history.csv") if r["days7"]!=""]
    own = {key(r):r for r in read("own.csv")}
    baseline = {key(r):r for r in read("forecast_oos.csv") if r["outcome"]=="days7"}
    for r in rows:
        for field in OWN:
            r[field] = own.get(key(r),{}).get(field,"")
    out = []
    for start, end in FOLDS:
        limit = date.fromisoformat(start) - timedelta(days=7)
        train = [r for r in rows if date.fromisoformat(r["date"])<limit]
        test = [r for r in rows if start<=r["date"]<=end]
        values = {model:predict(train,test,model,"days7") for model in ("active","depth","momentum")}
        for i,r in enumerate(test):
            g = baseline[key(r)]
            out.append(dict(date=r["date"],board=r["board"],id=r["id"],group=r["group"],
                            fold=g["fold"],outcome="days7",actual=g["actual"],G=g["G"],
                            **{name:v[i] for name,v in values.items()}))
    write("dimension_oos.csv",out)
    summary = []
    for fold in (*sorted({r["fold"] for r in out}),"pooled"):
        subset = [r for r in out if fold=="pooled" or r["fold"]==fold]
        metric = lambda name:mean(abs(float(r[name])-float(r["actual"])) for r in subset)
        for name in ("G","active","depth","momentum"):
            v = metric(name)
            summary.append(dict(fold=fold,model=name,events=len(subset),mae=v,improvement_vs_static_G=metric("G")-v))
    write("dimension_summary.csv",summary)
    print([(r["fold"],r["model"],round(r["improvement_vs_static_G"],4)) for r in summary if r["model"]!="G"])


if __name__=="__main__":
    main()
