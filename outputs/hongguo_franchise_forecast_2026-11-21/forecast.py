"""Forecast seven-day chart outcomes using nested feature blocks; only prior mature labels enter each fit."""
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BOARDS = ("hot", "real", "ai", "comic")
FOLDS = (("2026-11-02","2026-11-05"), ("2026-11-06","2026-11-09"), ("2026-11-10","2026-11-14"))
PRIMARY_OUTCOME = "days7"
OUTCOMES = (PRIMARY_OUTCOME, "day7", "top20_7")
OWN = ("heat","likes","favorites","rating")
HISTORY = ("linked","active_count","best_rank","momentum","seasons_observed","prior_chart_days","season_number")
MODELS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")
PENALTY = 10.0
GIANT = "7676739369444576281"


def read(name):
    with (HERE / name).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (HERE / name).open("w",encoding="utf-8-sig",newline="") as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def key(row):
    return row["date"],row["board"],row["id"]


def number(value):
    return np.nan if value is None or value == "" else float(value)


def design(rows, model, entry_categories):
    matrix = []
    for r in rows:
        rank = int(r["rank"])
        d = date.fromisoformat(r["date"])
        board = [r["board"] == b for b in BOARDS[1:]]
        # Fixed hinge locations make rankings near the extremes less constrained.
        v = [rank, max(rank-25,0), max(rank-75,0), *board,
             *((rank-50)*b for b in board), *(r["entry_type"]==t for t in entry_categories),
             np.sin(2*np.pi*d.weekday()/7), np.cos(2*np.pi*d.weekday()/7)]
        if model != "A":
            for field in OWN:
                x = number(r.get(field))
                if np.isfinite(x) and field != "rating":
                    assert x >= 0
                    x = np.log1p(x)
                v.append(x)
        if model == "E":
            v.append(float(number(r["asof_active_count"]) > 0))
        if model in ("C","D","F","G","H","I","J","active","depth","momentum"):
            prefix = "oracle_" if model in ("D","J") else "asof_"
            fields = HISTORY
            if model=="F":
                fields = ("linked","active_count","best_rank")
            elif model in ("G","H","J"):
                fields = ("linked","season_number")
            elif model=="active":
                fields = ("linked","season_number","active_count","best_rank")
            elif model=="depth":
                fields = ("linked","season_number","seasons_observed","prior_chart_days")
            elif model=="momentum":
                fields = ("linked","season_number","momentum")
            for field in fields:
                x = number(r[prefix+field])
                if np.isfinite(x) and field in ("active_count","seasons_observed","prior_chart_days","season_number"):
                    assert x >= 0
                    x = np.log1p(x)
                v.append(x)
        if model in ("H","I"):
            v.extend([float(r["complete_days_in_prior7"]), min(7, int(r["days_since_start"]))])
        matrix.append(v)
    return np.array(matrix,dtype=float)


def preprocess(train, test):
    # Drops unsupported/constant columns. Present vs missing is learned on training examples only.
    train_cols, test_cols = [], []
    for left, right in zip(train.T,test.T):
        observed = np.isfinite(left)
        if not observed.any():
            continue
        median = np.median(left[observed])
        for a,b in ((np.where(observed,left,median), np.where(np.isfinite(right),right,median)),
                    ((~observed).astype(float), (~np.isfinite(right)).astype(float))):
            sd = a.std()
            if sd > 1e-9:
                scaled = (a-a.mean())/sd
                # Ridge would silently downweight its penalty if a missingness flag
                # were repeated for several perfectly co-missing history fields.
                if any(np.allclose(scaled,old,rtol=0,atol=1e-10) or
                       np.allclose(scaled,-old,rtol=0,atol=1e-10) for old in train_cols):
                    continue
                train_cols.append(scaled)
                test_cols.append((b-a.mean())/sd)
    return (np.column_stack([np.ones(len(train)),*train_cols]),
            np.column_stack([np.ones(len(test)),*test_cols]))


def logistic(x, y, regularizer):
    beta = np.zeros(x.shape[1])
    beta[0] = np.log((y.sum()+0.5)/(len(y)-y.sum()+0.5))
    for _ in range(100):
        p = 1/(1+np.exp(-np.clip(x@beta,-35,35)))
        hessian = x.T@((p*(1-p))[:,None]*x)+regularizer
        step = np.linalg.solve(hessian, x.T@(p-y)+regularizer@beta)
        beta -= step
        if np.max(np.abs(step)) < 1e-8:
            return beta
    raise ValueError("Logistic fit did not converge")


def predict(train, test, model, outcome):
    entry_categories = sorted({r["entry_type"] for r in train})[1:]
    x, z = preprocess(design(train,model,entry_categories),design(test,model,entry_categories))
    y = np.array([int(r[outcome]) for r in train])
    penalty = PENALTY*np.eye(x.shape[1])
    penalty[0,0] = 0
    if outcome == PRIMARY_OUTCOME:
        beta = np.linalg.solve(x.T@x+penalty, x.T@y)
        return np.clip(z@beta,0,7)
    beta = logistic(x,y,penalty)
    return 1/(1+np.exp(-np.clip(z@beta,-35,35)))


def binary_scores(y, p):
    positives, negatives = y.sum(), len(y)-y.sum()
    if not positives or not negatives:
        return "", "", "", ""
    order = np.argsort(-p)
    sorted_probs, sorted_y = p[order],y[order]
    ends = np.r_[np.where(np.diff(sorted_probs)!=0)[0],len(y)-1]
    cumulative_pos = np.cumsum(sorted_y)[ends]
    cumulative_neg = ends+1-cumulative_pos
    precision = cumulative_pos/(ends+1)
    recall = cumulative_pos/positives
    fpr = cumulative_neg/negatives
    ap = sum(np.diff(np.r_[0,recall])*precision)
    auc = sum(np.diff(np.r_[0,fpr])*(recall+np.r_[0,recall[:-1]])/2)
    logits = np.log(np.clip(p,1e-10,1)/np.clip(1-p,1e-10,1))
    if positives < 5 or negatives < 5 or np.std(logits) < 1e-8:
        return auc, ap, "", ""
    try:
        intercept,slope = logistic(np.column_stack([np.ones(len(y)),logits]),y,np.diag([0.,1e-8]))
    except (ValueError,np.linalg.LinAlgError):
        return auc, ap, "", ""
    return auc,ap,intercept,slope


def summarize(predictions, count_info, scenario):
    summaries = []
    for fold in (*[a+"_"+b for a,b in FOLDS],"pooled"):
        for outcome in OUTCOMES:
            rows = [r for r in predictions if r["outcome"]==outcome and (fold=="pooled" or r["fold"]==fold)]
            if not rows:
                continue
            y = np.array([r["actual"] for r in rows])
            for model in MODELS:
                p = np.array([r[model] for r in rows])
                continuous = outcome==PRIMARY_OUTCOME
                auc,ap,ci,cs = ("","","","") if continuous else binary_scores(y,p)
                loss = np.abs(y-p) if continuous else (y-p)**2
                summaries.append(dict(scenario=scenario,fold=fold,outcome=outcome,model=model,
                                      train=count_info.get((fold,outcome),""),test=len(rows),positive="" if continuous else int(y.sum()),
                                      observed_mean=y.mean(),predicted_mean=p.mean(),metric="MAE" if continuous else "Brier",
                                      score=loss.mean(),roc_auc=auc,average_precision=ap,calibration_intercept=ci,calibration_slope=cs))
    return summaries


def run(rows, scenario):
    predictions = []
    count_info = {}
    for start, end in FOLDS:
        available_before = date.fromisoformat(start) - timedelta(days=7)
        fold = start+"_"+end
        for outcome in OUTCOMES:
            eligible = [r for r in rows if r[outcome] not in ("",None)
                        and (outcome != "top20_7" or int(r["rank"])>20)]
            train = [r for r in eligible if date.fromisoformat(r["date"]) < available_before]
            test = [r for r in eligible if start<=r["date"]<=end]
            assert train and test and max(date.fromisoformat(r["date"])+timedelta(days=7) for r in train) < date.fromisoformat(start)
            count_info[fold,outcome] = len(train)
            scores = {model:predict(train,test,model,outcome) for model in MODELS}
            for i,r in enumerate(test):
                predictions.append(dict(date=r["date"],board=r["board"],id=r["id"],group=r["group"],
                                        rank=r["rank"],entry_type=r["entry_type"],fold=fold,outcome=outcome,actual=int(r[outcome]),
                                        asof_linked=r["asof_linked"],oracle_linked=r["oracle_linked"],
                                        full_prior7=r["full_prior7"],
                                        **{model:values[i] for model,values in scores.items()}))
    basename = "forecast_oos.csv" if scenario=="main" else "forecast_no_giant_oos.csv"
    write(basename,predictions)
    return summarize(predictions,count_info,scenario)


def main():
    rows = read("history.csv")
    own = {key(r):r for r in read("own.csv")}
    assert len({key(r) for r in rows})==len(rows)
    for r in rows:
        metrics = own.get(key(r),{})
        r.update({col:metrics.get(col,"") for col in OWN})
    result = run(rows,"main")
    kept = [r for r in rows if r["group"].split(":")[-1]!=GIANT]
    assert 0 < len(kept) < len(rows)
    result.extend(run(kept,"no_giant"))
    write("roll_summary.csv",result)
    for r in result:
        if r["fold"]=="pooled" and r["model"] in ("B","C","D"):
            print(r["scenario"],r["outcome"],r["model"],r["test"],round(r["score"],6))


if __name__=="__main__":
    main()
