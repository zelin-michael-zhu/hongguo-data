"""A bounded feasibility pilot using existing published Hongguo snapshots."""

import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np


SOURCE = Path('/Users/zhuzelin/Desktop/fyp/outputs/hongguo_free_pilot_2026-11-18/history')
OUTPUT = Path(__file__).parent


def read_csv(name):
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def number(value):
    return float(value) if value else float('nan')


def log_count(value):
    return math.log1p(float(value)) if value else float('nan')


def fit_predict(train_x, train_y, test_x):
    """Fit fixed-penalty logistic regression with training-only preprocessing."""
    medians = np.nanmedian(train_x, axis=0)
    medians = np.where(np.isnan(medians), 0.0, medians)
    train_missing = np.isnan(train_x).astype(float)
    test_missing = np.isnan(test_x).astype(float)
    train = np.concatenate([np.where(np.isnan(train_x), medians, train_x), train_missing], axis=1)
    test = np.concatenate([np.where(np.isnan(test_x), medians, test_x), test_missing], axis=1)
    means = train.mean(axis=0)
    deviations = train.std(axis=0)
    deviations = np.where(deviations < 1e-8, 1.0, deviations)
    train = np.column_stack([np.ones(len(train)), (train - means) / deviations])
    test = np.column_stack([np.ones(len(test)), (test - means) / deviations])
    weights = np.zeros(train.shape[1])
    penalty = np.ones(train.shape[1])
    penalty[0] = 0.0

    def objective(parameters):
        logits = train @ parameters
        return np.sum(np.logaddexp(0.0, logits) - train_y * logits) + 0.5 * np.sum(penalty * parameters ** 2)

    for _ in range(35):
        logits = np.clip(train @ weights, -35.0, 35.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        gradient = train.T @ (probabilities - train_y) + penalty * weights
        curvature = probabilities * (1.0 - probabilities)
        hessian = train.T @ (curvature[:, None] * train) + np.diag(penalty + 1e-8)
        step = np.linalg.solve(hessian, gradient)
        rate = 1.0
        current_loss = objective(weights)
        while objective(weights - rate * step) > current_loss and rate > 1e-5:
            rate *= 0.5
        weights -= rate * step
        if np.max(np.abs(rate * step)) < 1e-6:
            break
    return 1.0 / (1.0 + np.exp(-np.clip(test @ weights, -35.0, 35.0)))


def evaluate(labels, probabilities):
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities)
    _, inverse, counts = np.unique(probabilities, return_inverse=True, return_counts=True)
    end_ranks = np.cumsum(counts)
    average_ranks = end_ranks - (counts - 1) / 2.0
    positives = labels.sum()
    negatives = len(labels) - positives
    auc = (average_ranks[inverse][labels == 1].sum() - positives * (positives + 1) / 2.0) / (positives * negatives)
    clipped = np.clip(probabilities, 1e-8, 1.0 - 1e-8)
    return {
        'rows': len(labels),
        'exit_events': int(positives),
        'exit_rate': float(labels.mean()),
        'roc_auc': float(auc),
        'brier_score': float(np.mean((probabilities - labels) ** 2)),
        'log_loss': float(-np.mean(labels * np.log(clipped) + (1 - labels) * np.log(1 - clipped))),
    }


def main():
    daily = {(row['date'], row['id']): row for row in read_csv('drama_daily.csv')}
    boards = defaultdict(dict)
    for row in read_csv('board_daily.csv'):
        boards[(row['date'], row['board'])][row['id']] = row
    board_names = sorted({board for _, board in boards})
    samples = []
    for (origin, board), entries in sorted(boards.items()):
        origin_date = date.fromisoformat(origin)
        target = (origin_date + timedelta(days=1)).isoformat()
        next_entries = boards.get((target, board), {})
        if len(entries) != 100 or len(next_entries) != 100:
            continue
        previous_date = (origin_date - timedelta(days=1)).isoformat()
        previous_board = boards.get((previous_date, board), {})
        for series_id, entry in entries.items():
            current = daily.get((origin, series_id), {})
            previous = daily.get((previous_date, series_id), {})
            previous_rank = previous_board.get(series_id, {}).get('rank', '')
            rank = int(entry['rank'])
            features = [rank / 100.0] + [float(board == name) for name in board_names[1:]]
            extended = features + [
                log_count(current.get('heat', '')),
                log_count(current.get('fav', '')),
                log_count(current.get('like', '')),
                number(current.get('rating', '')),
                log_count(current.get('rating_count', '')),
                number(current.get('age_days', '')),
                (rank - int(previous_rank)) / 100.0 if previous_rank else float('nan'),
                log_count(current.get('heat', '')) - log_count(previous.get('heat', '')),
            ]
            samples.append({
                'origin': origin,
                'target': target,
                'board': board,
                'id': series_id,
                'label': int(series_id not in next_entries),
                'baseline': features,
                'extended': extended,
            })

    predictions = []
    origins = sorted({row['origin'] for row in samples if row['target'] >= '2026-11-08'})
    for origin in origins:
        training = [row for row in samples if row['target'] <= origin]
        testing = [row for row in samples if row['origin'] == origin]
        labels = np.array([row['label'] for row in training], dtype=float)
        estimates = {}
        for name in ['baseline', 'extended']:
            train_x = np.array([row[name] for row in training], dtype=float)
            test_x = np.array([row[name] for row in testing], dtype=float)
            estimates[name] = fit_predict(train_x, labels, test_x)
        for index, row in enumerate(testing):
            predictions.append({
                'forecast_origin': origin,
                'target_date': row['target'],
                'board': row['board'],
                'series_id': row['id'],
                'exit_next_day': row['label'],
                'rank_baseline_probability': float(estimates['baseline'][index]),
                'extended_probability': float(estimates['extended'][index]),
            })

    summary = {
        'task': 'Next-day exit from the same published Top100 board among currently listed titles',
        'eligible_labels': len(samples),
        'eligible_exit_events': sum(row['label'] for row in samples),
        'evaluation': 'Expanding daily training. Each origin uses labels observed no later than the origin.',
        'test_target_dates': sorted({row['target_date'] for row in predictions}),
        'preprocessing': 'Training-only median imputation, missingness indicators, and standardization.',
        'model': 'Logistic regression with fixed L2 penalty 1.0, no hyperparameter search.',
        'excluded_features': ['review_count because of observed jumps', 'catalog.last_seen', 'catalog.boards_seen', 'final catalog metadata'],
        'rank_baseline': evaluate([row['exit_next_day'] for row in predictions], [row['rank_baseline_probability'] for row in predictions]),
        'extended_model': evaluate([row['exit_next_day'] for row in predictions], [row['extended_probability'] for row in predictions]),
        'limitations': ['Ten test dates only', 'Repeated titles and overlapping boards', 'Results apply only to currently listed titles', 'No causal identification or originality claim'],
    }
    (OUTPUT / 'prediction_pilot_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUTPUT / 'prediction_pilot_rows.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
