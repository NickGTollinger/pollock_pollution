"""Pollock's original CSV-export metric semantics, implemented with Counters.

See third_party/pollock for the upstream reference, weights and provenance.
Do not replace these conventions with the project's corrected recovery metrics.
"""
from collections import Counter
from functools import lru_cache

METRICS = [f'{group}_{measure}' for group in ('header', 'record', 'cell')
           for measure in ('precision', 'recall', 'f1')]


@lru_cache(maxsize=50000)
def normalized(value):
    # Reuse the same adapted normalizer as the configured benchmark. Import
    # lazily so CSV-only report generation needs only the Python standard library.
    from pollock.data_types import normalize_cell
    return normalize_cell(value)


def original_measures(expected, actual, empty_expected_perfect=False):
    """Upstream names P=intersection/expected, R=intersection/actual."""
    if not expected and empty_expected_perfect:
        return (1.0, 1.0, 1.0)
    matches = sum((Counter(expected) & Counter(actual)).values())
    if not matches:
        return (0.0, 0.0, 0.0)
    p, r = matches / len(expected), matches / len(actual)
    return p, r, 2 * p * r / (p + r)


def score_rows(expected, actual, success=True):
    """Evaluate canonical CSV rows, retaining upstream's original edge cases.

    csv.writer exports SQL NULL as empty text; both must be represented as ''
    here. Header metadata is intentionally not used: upstream treats row 0 as
    header even for a header-free file. Cells are raw and include that row.
    """
    if not success:
        return dict(success=0, **dict.fromkeys(METRICS, 0.0))
    if not expected:
        return dict(success=1, **dict.fromkeys(METRICS, 1.0))
    expected_header = [normalized(v) for v in expected[0]]
    actual_header = [normalized(v) for v in actual[0]] if actual else []
    header = original_measures(expected_header, actual_header, True)
    # Concatenation is deliberate for compatibility. It can equate records
    # with different cell boundaries; our separate recovery grade uses tuples.
    e_records = [''.join(normalized(v) for v in row) for row in expected[1:]]
    a_records = [''.join(normalized(v) for v in row) for row in actual[1:]]
    record = original_measures(e_records, a_records, True)
    cell = original_measures([v for row in expected for v in row],
                            [v for row in actual for v in row], True)
    return dict(success=1, **dict(zip(METRICS, header + record + cell)))


def exported_rows(payload):
    """Recreate this project's csv.writer export using authoritative JSON."""
    rows = ([payload['header']] if payload['parameters']['header_lines'] else []) + payload['records']
    return [['' if value is None else str(value) for value in row] for row in rows]


def aggregate(cases, weights):
    """Simple and survey-weighted scores on exactly the selected filenames."""
    if not cases:
        raise ValueError('No cases to aggregate')
    missing = sorted({r['filename'] for r in cases} - weights.keys())
    if missing:
        raise ValueError(f'Missing upstream weights: {missing[:5]}')
    total_weight = sum(weights[r['filename']] for r in cases)
    if total_weight <= 0:
        raise ValueError('Selected weights must have positive total')
    totals = [r['success'] + sum(r[m] for m in METRICS) for r in cases]
    return (sum(totals) / len(cases),
            sum(t * weights[r['filename']] for t, r in zip(totals, cases)) / total_weight)
