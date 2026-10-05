"""Pollock-inspired metrics with explicit conventional precision/recall."""
from collections import Counter
from functools import lru_cache
from pollock.data_types import normalize_cell

@lru_cache(maxsize=20000)
def normalize(value):
    # Preserve SQL NULL separately from a legitimate empty CSV cell.
    return ('null',) if value is None else ('value', normalize_cell(str(value)))


def measures(expected, actual):
    # Multiset intersection counts duplicates without matching one value twice.
    expected, actual = Counter(expected), Counter(actual)
    matches = sum((expected & actual).values())
    n_expected, n_actual = sum(expected.values()), sum(actual.values())
    if not n_expected and not n_actual:
        return 1.0, 1.0, 1.0
    precision = matches / n_actual if n_actual else 0.0
    recall = matches / n_expected if n_expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def evaluate(expected_header, expected_rows, header, rows):
    # Scores ignore row order. Record tuples preserve field order/boundaries;
    # cell scores compare values only, so they cannot detect shifted columns.
    groups = [
        ('header', [normalize(x) for x in expected_header], [normalize(x) for x in header]),
        ('record', [tuple(normalize(x) for x in row) for row in expected_rows],
                   [tuple(normalize(x) for x in row) for row in rows]),
        ('cell', [normalize(x) for row in expected_rows for x in row],
                 [normalize(x) for row in rows for x in row]),
    ]
    scores = {}
    for name, expected, actual in groups:
        for metric, value in zip(('precision', 'recall', 'f1'), measures(expected, actual)):
            scores[f'{name}_{metric}'] = value
    return scores

METRIC_NAMES = [f'{group}_{metric}' for group in ('header', 'record', 'cell')
                for metric in ('precision', 'recall', 'f1')]
