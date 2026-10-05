# Run the 10 Pollock pollutions that we selected
import argparse
import contextlib
import csv
import io
import json
import platform
import time
import warnings
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

from benchmark.adapters import LOADERS
from benchmark.cases import category
from benchmark.evaluation import evaluate, METRIC_NAMES

ROOT = Path(__file__).resolve().parent


def expected_content(path, p):
    with path.open(encoding='utf-8', newline='') as file:
        rows = list(csv.reader(file))
    # Expected files flatten multirow headers into one canonical header row.
    if p['header_lines'] and rows:
        return rows[0], rows[1:]
    return [], rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loaders', nargs='+', choices=list(LOADERS), default=list(LOADERS))
    parser.add_argument('--smoke', action='store_true', help='One file per category plus baseline')
    parser.add_argument('--category', help='One category name, always with baseline')
    parser.add_argument('--output', default='results/configured', help='Separate output directory for this run')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'data/pollock_manifest.json').read_text(encoding='utf-8'))
    selected = [(case, category(case)) for case in manifest if category(case)]
    available = {kind for _, kind in selected}
    if len(available) != 11:
        raise RuntimeError(f'Expected baseline plus ten categories; found {sorted(available)}')
    if args.category:
        if args.category not in available:
            parser.error(f'Unknown category. Choose from: {", ".join(sorted(available))}')
        selected = [(case, kind) for case, kind in selected if kind in ('baseline', args.category)]
    if args.smoke:
        seen = set()
        selected = [(case, kind) for case, kind in selected if not (kind in seen or seen.add(kind))]
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    print(f'Selected {len(selected)} files across {len({kind for _, kind in selected})} categories.')
    # Baseline errors indicate environment/configuration trouble. Stop before
    # treating a missing executable, server or dependency as a pollution failure.
    base_case = next(case for case, kind in selected if kind == 'baseline')
    base_path = ROOT / 'data/polluted/pollock' / base_case['filename']
    base_p = json.loads((ROOT / 'data/parameters/pollock' / (base_case['filename'] + '_parameters.json')).read_text())
    expected_header, expected_rows = expected_content(ROOT / 'data/expected/pollock/source.csv', base_p)
    for name in args.loaders:
        header, rows = LOADERS[name](base_path, base_p)
        if header != expected_header or rows != expected_rows:
            raise RuntimeError(f'{name}: configured baseline differs from expected content. Resolve before benchmarking.')
        print(f'{name}: configured baseline passed')
    metadata = {'python': platform.python_version(), 'platform': platform.platform(),
                'mode': 'configured', 'smoke': args.smoke,
                'loaders': args.loaders, 'file_count': len(selected), 'packages': {}}
    for package in ('pandas', 'clevercsv', 'mysql-connector-python'):
        try:
            metadata['packages'][package] = version(package)
        except Exception:
            pass
    (output / 'run_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    fields = ['loader', 'category', 'filename', 'success', 'exact_match', 'header_cells', 'records',
              'adapter_seconds', 'diagnostic_count', 'error'] + METRIC_NAMES
    totals = defaultdict(list)
    with (output / 'case_results.csv').open('w', encoding='utf-8', newline='') as report:
        writer = csv.DictWriter(report, fieldnames=fields)
        writer.writeheader()
        for index, (case, kind) in enumerate(selected, 1):
            filename = case['filename']
            path = ROOT / 'data/polluted/pollock' / filename
            p = json.loads((ROOT / 'data/parameters/pollock' / (filename + '_parameters.json')).read_text())
            expected_header, expected_rows = expected_content(ROOT / 'data/expected/pollock' / filename, p)
            for name in args.loaders:
                log = io.StringIO()
                record = dict(loader=name, category=kind, filename=filename,
                              success=0, exact_match=False, header_cells=0, records=0,
                              error='', **{metric: 0.0 for metric in METRIC_NAMES})
                header, rows = [], []
                # Timing includes connection/import/retrieval, but excludes scoring
                # and output serialization. It is not pure parser throughput.
                started = time.perf_counter()
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    try:
                        header, rows = LOADERS[name](path, p)
                        record.update(success=1, header_cells=len(header), records=len(rows),
                                      exact_match=header == expected_header and rows == expected_rows)
                    except Exception as error:
                        record['error'] = f'{type(error).__name__}: {error}'
                record['adapter_seconds'] = time.perf_counter() - started
                for warning in caught:
                    log.write(f'{warning.category.__name__}: {warning.message}\n')
                diagnostics = log.getvalue()
                record['diagnostic_count'] = len(diagnostics.splitlines())
                # Returning data is success even when it is malformed. Exceptions
                # retain zero scores, and exact match separately checks raw content.
                if record['success']:
                    record.update(evaluate(expected_header, expected_rows, header, rows))
                destination = output / 'outputs' / name
                destination.mkdir(parents=True, exist_ok=True)
                # JSON preserves NULL, empty headers and row boundaries exactly.
                payload = {'success': record['success'], 'header': header, 'records': rows,
                           'error': record['error'], 'diagnostics': diagnostics,
                           'parameters': p, 'category': kind}
                (destination / (filename + '.json')).write_text(json.dumps(payload, indent=2), encoding='utf-8')
                csv_path = destination / filename
                if record['success']:
                    with csv_path.open('w', encoding='utf-8', newline='') as file:
                        csv_writer = csv.writer(file)
                        if p['header_lines']:
                            csv_writer.writerow(header)
                        csv_writer.writerows(rows)
                elif csv_path.exists():
                    csv_path.unlink()  # Remove stale success output from a prior run.
                writer.writerow(record)
                totals[(name, kind)].append(record)
            report.flush()
            if index % 100 == 0 or index == len(selected):
                print(f'Completed {index}/{len(selected)} files')
    summary_fields = ['loader', 'category', 'files', 'success_rate', 'exact_match_rate', 'mean_adapter_seconds'] + METRIC_NAMES
    with (output / 'category_summary.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=summary_fields)
        writer.writeheader()
        for (name, kind), records in sorted(totals.items()):
            row = dict(loader=name, category=kind, files=len(records),
                       success_rate=sum(r['success'] for r in records) / len(records),
                       exact_match_rate=sum(r['exact_match'] for r in records) / len(records),
                       mean_adapter_seconds=sum(r['adapter_seconds'] for r in records) / len(records))
            # Per-file macro averages include failed loads as zero. Categories
            # have unequal sizes, so do not treat a pooled mean as a fair ranking.
            row.update({metric: sum(r[metric] for r in records) / len(records) for metric in METRIC_NAMES})
            writer.writerow(row)
    print('Results:', output)


if __name__ == '__main__':
    main()
