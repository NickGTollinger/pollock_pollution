"""Score an existing configured run; never invokes a CSV loader or database."""
import argparse
import csv
import hashlib
import html
import json
import math
import platform
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRICS = [f'{g}_{m}' for g in ('header', 'record', 'cell') for m in ('precision', 'recall', 'f1')]
CATEGORIES = ('missing_header', 'two_row_header', 'preamble', 'extra_record_separator',
              'missing_record_separator', 'extra_unescaped_quote', 'semicolon_delimiter',
              'tab_delimiter', 'single_quote_character', 'backslash_escape')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def binary(value):
    if str(value).lower() in ('1', 'true'):
        return 1
    if str(value).lower() in ('0', 'false'):
        return 0
    raise ValueError(f'Expected a binary flag, got {value!r}')


def validate_run(run):
    """Reject incomplete or inconsistent input before creating any report."""
    metadata = json.loads((run / 'run_metadata.json').read_text(encoding='utf-8-sig'))
    if metadata.get('mode') != 'configured':
        raise ValueError('This reporter expects configured-run output')
    rows = read_csv(run / 'case_results.csv')
    if not rows:
        raise ValueError('case_results.csv is empty')
    seen, groups, filenames, file_categories = set(), defaultdict(list), defaultdict(set), {}
    for r in rows:
        if not r['loader'].replace('_', '').isalnum():
            raise ValueError('Unsafe loader name in result')
        key = (r['loader'], r['filename'])
        if key in seen:
            raise ValueError(f'Duplicate loader/file result: {key}')
        seen.add(key)
        if Path(r['filename']).name != r['filename'] or '/' in r['filename'] or '\\' in r['filename']:
            raise ValueError('Unsafe filename in result')
        if r['category'] not in ('baseline',) + CATEGORIES:
            raise ValueError(f'Unknown category: {r["category"]}')
        previous = file_categories.setdefault(r['filename'], r['category'])
        if previous != r['category']:
            raise ValueError('A filename has inconsistent category labels')
        r['success'], r['exact_match'] = binary(r['success']), binary(r['exact_match'])
        for field in METRICS + ['adapter_seconds']:
            r[field] = float(r[field])
            if not math.isfinite(r[field]) or r[field] < 0 or (field in METRICS and r[field] > 1):
                raise ValueError(f'Invalid {field}: {key}')
        for field in ('diagnostic_count', 'header_cells', 'records'):
            r[field] = int(r[field])
            if r[field] < 0:
                raise ValueError(f'Negative {field}: {key}')
        if bool(r['error']) != (not r['success']):
            raise ValueError(f'Error/success mismatch: {key}')
        if not r['success'] and (r['exact_match'] or any(r[m] for m in METRICS)):
            raise ValueError(f'Nonzero correctness on failed load: {key}')
        if r['exact_match'] and (not r['success'] or any(r[m] != 1 for m in METRICS)):
            raise ValueError(f'Exact match with imperfect metrics: {key}')
        for group in ('header', 'record', 'cell'):
            p, recall, f1 = [r[f'{group}_{m}'] for m in ('precision', 'recall', 'f1')]
            expected = 2*p*recall/(p+recall) if p+recall else 0
            if not math.isclose(f1, expected, abs_tol=1e-10):
                raise ValueError(f'Inconsistent F1: {key}, {group}')
        groups[r['loader'], r['category']].append(r)
        filenames[r['loader']].add(r['filename'])
    if set(filenames) != set(metadata['loaders']) or len(metadata['loaders']) != len(filenames):
        raise ValueError('Loader selection disagrees with run_metadata.json')
    first = next(iter(filenames.values()))
    if any(files != first for files in filenames.values()) or len(first) != metadata['file_count']:
        raise ValueError('Incomplete run: loaders do not share the declared input set')
    for loader in filenames:
        baseline = groups.get((loader, 'baseline'), [])
        if len(baseline) != 1 or not baseline[0]['exact_match']:
            raise ValueError(f'{loader}: clean baseline missing or not exact')
    # Check the supplied summary independently. Never aggregate rounded summary data.
    summary = read_csv(run / 'category_summary.csv')
    if len(summary) != len(groups) or len({(r['loader'], r['category']) for r in summary}) != len(groups):
        raise ValueError('category_summary.csv has missing or duplicate groups')
    for r in summary:
        g = groups.get((r['loader'], r['category']))
        if not g or int(r['files']) != len(g):
            raise ValueError('Summary group/count mismatch')
        for field in METRICS + ['success_rate', 'exact_match_rate', 'mean_adapter_seconds']:
            src = {'success_rate':'success', 'exact_match_rate':'exact_match',
                   'mean_adapter_seconds':'adapter_seconds'}.get(field, field)
            if not math.isclose(float(r[field]), statistics.fmean(x[src] for x in g), abs_tol=1e-10):
                raise ValueError(f'Summary mismatch: {r["loader"]}, {r["category"]}, {field}')
    return metadata, rows, groups


def percentile(values, fraction):
    """Linear interpolation at (n-1)*fraction (inclusive quartiles)."""
    ordered = sorted(values)
    position = (len(ordered)-1)*fraction
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(position-lo)


def describe(values, prefix):
    return {f'{prefix}_{label}': value for label, value in {
        'mean':statistics.fmean(values), 'median':statistics.median(values),
        'min':min(values), 'q25':percentile(values, .25), 'q75':percentile(values, .75),
        'max':max(values), 'population_sd':statistics.pstdev(values)}.items()}


def category_statistics(groups):
    output = []
    for (loader, category), rows in sorted(groups.items()):
        n = len(rows)
        r = dict(loader=loader, category=category, files=n,
                 completed=sum(x['success'] for x in rows),
                 failed=sum(not x['success'] for x in rows),
                 exact=sum(x['exact_match'] for x in rows),
                 completed_inexact=sum(x['success'] and not x['exact_match'] for x in rows),
                 with_diagnostics=sum(x['diagnostic_count'] > 0 for x in rows),
                 diagnostic_lines=sum(x['diagnostic_count'] for x in rows))
        for name, count in [('completion_rate','completed'), ('exact_match_rate','exact'),
                            ('diagnostic_rate','with_diagnostics')]:
            r[name] = r[count]/n
        for metric in METRICS:
            r[metric] = statistics.fmean(x[metric] for x in rows)
        for metric in ('record_f1', 'cell_f1', 'adapter_seconds'):
            r.update(describe([x[metric] for x in rows], metric))
        output.append(r)
    return output


def loader_statistics(rows, categories):
    output = []
    for loader in sorted({x['loader'] for x in rows}):
        g = [x for x in rows if x['loader'] == loader and x['category'] != 'baseline']
        c = [x for x in categories if x['loader'] == loader and x['category'] != 'baseline']
        if not g:
            raise ValueError('At least one pollution category is required')
        r = dict(loader=loader, pollution_categories=len(c), files=len(g),
                 baseline_exact=True, completed=sum(x['success'] for x in g),
                 failed=sum(not x['success'] for x in g), exact=sum(x['exact_match'] for x in g),
                 completed_inexact=sum(x['success'] and not x['exact_match'] for x in g),
                 with_diagnostics=sum(x['diagnostic_count'] > 0 for x in g))
        for label, field in [('header','header_f1'), ('record','record_f1'), ('cell','cell_f1'),
                             ('exact','exact_match_rate'), ('completion','completion_rate')]:
            r[f'balanced_{label}_grade'] = 100*statistics.fmean(x[field] for x in c)
        r['record_recovery_grade'] = r['balanced_record_grade']
        r['pooled_completion_rate'] = r['completed']/len(g)
        r['pooled_exact_match_rate'] = r['exact']/len(g)
        output.append(r)
    # Equal scores receive equal ranks (competition ranking, tolerance 1e-9).
    for r in output:
        r['record_recovery_rank'] = 1 + sum(x['record_recovery_grade'] > r['record_recovery_grade'] + 1e-9 for x in output)
    return sorted(output, key=lambda x: (-x['record_recovery_grade'], x['loader']))


def original_pollock(run, project, rows, groups, output):
    from benchmark.pollock_scoring import score_rows, exported_rows, aggregate, METRICS as original_metrics
    weights_path = ROOT / 'third_party/pollock/pollock_weights.json'
    weights = json.loads(weights_path.read_text())
    if any(not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError('Invalid upstream weights')
    missing = sorted({r['filename'] for r in rows} - weights.keys())
    if missing:
        raise ValueError(f'Missing upstream weights: {missing[:5]}')
    results, expected_cache = [], {}
    output_digest, expected_digest = hashlib.sha256(), hashlib.sha256()
    for index, row in enumerate(rows, 1):
        loader, filename = row['loader'], row['filename']
        path = run / 'outputs' / loader / (filename + '.json')
        data = path.read_bytes()
        output_digest.update(f'{loader}/{filename}\0'.encode() + data)
        payload = json.loads(data)
        if payload['category'] != row['category'] or binary(payload['success']) != row['success']:
            raise ValueError(f'Output JSON metadata mismatch: {path}')
        if payload['error'] != row['error'] or len(payload['diagnostics'].splitlines()) != row['diagnostic_count']:
            raise ValueError(f'Output JSON diagnostics mismatch: {path}')
        if filename not in expected_cache:
            expected_path = project / 'data/expected/pollock' / filename
            expected_data = expected_path.read_bytes()
            expected_digest.update(filename.encode() + b'\0' + expected_data)
            with expected_path.open(encoding='utf-8-sig', newline='') as file:
                expected_cache[filename] = list(csv.reader(file))
        expected = expected_cache[filename]
        actual = exported_rows(payload)
        if row['success']:
            p = payload['parameters']
            expected_header = expected[0] if p['header_lines'] and expected else []
            expected_records = expected[1:] if p['header_lines'] and expected else expected
            if (payload['header'] == expected_header and payload['records'] == expected_records) != bool(row['exact_match']):
                raise ValueError(f'Output JSON exact-match mismatch: {path}')
            if len(payload['header']) != row['header_cells'] or len(payload['records']) != row['records']:
                raise ValueError(f'Output JSON dimensions mismatch: {path}')
        metrics = score_rows(expected, actual, bool(row['success']))
        results.append(dict(loader=loader, category=row['category'], filename=filename,
                            upstream_weight=weights[filename], **metrics))
        if index % 2000 == 0:
            print(f'Rescored {index}/{len(rows)} saved outputs')
    write_csv(output / 'pollock_case_scores.csv', results)
    summaries = []
    for loader in sorted({r['loader'] for r in rows}):
        cases = [r for r in results if r['loader'] == loader]
        simple, weighted = aggregate(cases, weights)
        summaries.append(dict(loader=loader, files=len(cases), includes_baseline=True,
                              pollock_simple_subset=simple, pollock_weighted_subset=weighted,
                              selected_weight_sum=sum(weights[r['filename']] for r in cases),
                              **{m:statistics.fmean(r[m] for r in cases) for m in ['success']+original_metrics}))
    write_csv(output / 'pollock_scores.csv', summaries)
    by_category = []
    for loader, category in sorted(groups):
        cases = [r for r in results if r['loader'] == loader and r['category'] == category]
        simple, weighted = aggregate(cases, weights)
        by_category.append(dict(loader=loader, category=category, files=len(cases),
                                pollock_simple=simple, pollock_weighted=weighted))
    write_csv(output / 'pollock_category_scores.csv', by_category)
    return summaries, {'saved_outputs_sha256':output_digest.hexdigest(),
                       'expected_content_sha256':expected_digest.hexdigest(),
                       'weights_sha256':sha256(weights_path)}


def write_csv(path, rows):
    if rows:
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |'] +
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def make_report(meta, loaders, categories, original, errors, output):
    full = not meta.get('smoke') and meta['file_count'] == 2175
    scope = 'Full configured selection' if full else 'Partial/smoke selection; exploratory grades only'
    md = ['# CSV Loader Evaluation', '', scope, '',
          f"{len(loaders)} loaders; {meta['file_count']:,} files per loader (including baseline). "
          f"{loaders[0]['pollution_categories']} pollution categories; one source dataset.", '',
          '## Recovery grades (0–100)', '',
          'Each grade averages within a pollution category, then gives each selected category equal weight. '
          'The clean baseline is excluded. Failed loads receive zero. No letter-grade thresholds are imposed.', '',
          table(['Loader','Record grade','Header grade','Cell grade','Balanced exact %','Balanced completion %'],
                [[r['loader'],*[f'{r[k]:.2f}' for k in ('record_recovery_grade','balanced_header_grade',
                'balanced_cell_grade','balanced_exact_grade','balanced_completion_grade')]] for r in loaders]), '',
          'Record grade is the primary project grade. A grade of 99 means high average record recovery, '
          'not that 99% of complete files were correct. Exact match compares raw values and order; F1 uses '
          'normalization and ignores record order. Cell F1 ignores cell positions. A high cell grade can coexist '
          'with shifted fields. Header-free cases have vacuously perfect header scores.', '',
          '## Actual outcomes across pollution variants', '',
          'These counts exclude the clean baseline and are pooled across files, rather than balanced by category.', '',
          table(['Loader','Files','Completed','Exceptions','Exact','Completed, inexact','With diagnostics'],
                [[r[k] for k in ('loader','files','completed','failed','exact','completed_inexact','with_diagnostics')] for r in loaders]), '',
          'Completed, inexact means the full raw table differs; it can include normalized-equivalent values. '
          'Diagnostics are captured messages/warnings, not necessarily fatal errors. Categories are unequally sized.', '',
          '## Record recovery by pollution', '',
          table(['Category','Cases per loader']+[r['loader'] for r in loaders],
                [[c, next(r['files'] for r in categories if r['category']==c)]+[
                    f"{100*next(r['record_f1'] for r in categories if r['category']==c and r['loader']==l['loader']):.2f}"
                    for l in loaders] for c in CATEGORIES if any(r['category']==c for r in categories)]), '',
          'Entries are mean record F1 × 100. The clean baseline matched exactly for every loader.', '',
          '## Original Pollock scoring (0–10)', '']
    if original:
        md += [table(['Loader','Simple, selected subset','Survey-weighted, selected subset'],
                     [[r['loader'], f"{r['pollock_simple_subset']:.4f}", f"{r['pollock_weighted_subset']:.4f}"] for r in original]), '',
               'Original scoring sums success and nine original precision/recall/F1 measures. Both scores include '
               'baseline. Simple scoring gives every selected file equal weight; weighted scoring uses upstream '
               'filename weights renormalized over the selected files. This is a subset score, not a reproduction '
               'of the paper’s full benchmark score. Missing categories are not assigned zero or imputed.', '',
               'The original evaluator treats the first row as header, concatenates record fields, and compares raw '
               'cells including headers. It labels intersection/expected as precision and intersection/returned as '
               'recall. Those conventions are retained. SQL NULL becomes empty text for this CSV-export score, '
               'while our recovery metrics distinguish NULL. Normalization uses the project’s adapted Pollock '
               'normalizer and the reporting environment’s dependencies.', '']
    else:
        md += ['Not requested. Rerun with `--pollock` to rescore the saved JSON outputs and expected CSVs.', '']
    md += ['## Findings', '']
    best = loaders[0]
    md.append(f"- Highest category-balanced record grade: {best['loader']} ({best['record_recovery_grade']:.2f}/100).")
    for l in loaders:
        c = [r for r in categories if r['loader']==l['loader'] and r['category']!='baseline']
        worst = min(c, key=lambda r:r['record_f1'])
        md.append(f"- {l['loader']}: lowest category mean is {worst['category']} "
                  f"({100*worst['record_f1']:.2f}/100, {worst['files']} case(s)); "
                  f"{l['failed']:,} exceptions and {l['completed_inexact']:,} completed, inexact outputs.")
    md += ['', '## Distributions and interpretation', '',
           'category_statistics.csv contains mean, median, min, 25th/75th percentiles, max, and population '
           'standard deviation for record/cell F1 and adapter time. Quartiles use linear interpolation at '
           '(n−1)×p. A one-case category has identical quantiles and zero spread; that does not establish reliability.', '',
           'These are descriptive statistics over correlated positional mutations of one dataset. There are no '
           'confidence intervals, significance tests, or claims about generalization. Seven pollution categories '
           'have one case each in the full selection. Rank changes under different weightings are expected.', '',
           'Configured metadata is supplied to adapters. The non-Pandas two-row-header limitation is in our '
           'adapter implementation. This is a comparison of these integrations and versions. SQL tools and '
           'Python libraries have different configuration requirements.', '',
           'Timing includes connection/process/table setup, parsing, and retrieval. It is a single run per case, '
           'not a repeated throughput experiment. Database versions and server settings are absent from the '
           'original run metadata. Keep those separately for reproducibility.', '',
           '## Output files', '',
           '- loader_scores.csv: grades and pooled outcome counts (baseline excluded).',
           '- category_statistics.csv: category-level metrics and distributions (baseline separate).',
           '- failure_summary.csv: exception counts by loader/category/error class.',
           '- pollock_scores.csv, pollock_category_scores.csv, pollock_case_scores.csv: original scoring when requested.',
           '- report_metadata.json: validation, source hashes, reporting environment and scoring definitions.', '',
           'Sources: supplied case_results.csv, category_summary.csv, run_metadata.json; original scoring '
           'additionally reads outputs/<loader>/*.json and data/expected/pollock/*.csv. '
           '[Pollock paper, §3.4](https://www.vldb.org/pvldb/vol16/p1870-vitagliano.pdf); '
           '[upstream evaluator](https://github.com/HPI-Information-Systems/Pollock/blob/main/evaluate.py).', '']
    markdown = '\n'.join(md)
    (output/'report.md').write_text(markdown, encoding='utf-8')
    # Render the controlled Markdown subset without a third-party dependency.
    def inline(text):
        escaped = html.escape(text)
        escaped = re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", r'<a href="\2">\1</a>', escaped)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    parts = []
    for line in md:
        if '\n' in line and line.startswith('|'):
            lines = line.splitlines()
            parts.append('<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(x.strip())+'</th>' for x in lines[0].strip('|').split('|'))+'</tr></thead><tbody>')
            for body in lines[2:]:
                parts.append('<tr>'+''.join('<td>'+html.escape(x.strip())+'</td>' for x in body.strip('|').split('|'))+'</tr>')
            parts.append('</tbody></table></div>')
        elif line.startswith('#'):
            level = len(line)-len(line.lstrip('#'))
            parts.append(f'<h{level}>'+html.escape(line.lstrip('# '))+f'</h{level}>')
        elif line:
            parts.append('<p>'+inline(line)+'</p>')
    # An inline SVG heatmap makes category differences visible; exact numbers
    # and case counts remain available in the adjacent table and title tooltips.
    present = [c for c in CATEGORIES if any(r['category']==c for r in categories)]
    svg = ['<h2>Record recovery heatmap</h2><p>Mean record F1 × 100. Darker cells indicate higher recovery.</p>',
           f'<svg role="img" aria-label="Record recovery by loader and pollution" viewBox="0 0 1000 {75+42*len(present)}">']
    for j,l in enumerate(loaders):
        svg.append(f'<text x="{320+130*j}" y="25" text-anchor="middle">{html.escape(l["loader"])}</text>')
    for i,c in enumerate(present):
        y = 45+42*i
        svg.append(f'<text x="5" y="{y+23}">{html.escape(c)}</text>')
        for j,l in enumerate(loaders):
            v = next(r['record_f1'] for r in categories if r['category']==c and r['loader']==l['loader'])
            light = 96-65*v
            svg.append(f'<rect x="{260+130*j}" y="{y}" width="120" height="34" rx="4" fill="hsl(205 65% {light:.1f}%)"><title>{html.escape(c)} / {html.escape(l["loader"])}: {v*100:.2f}</title></rect>')
            svg.append(f'<text x="{320+130*j}" y="{y+23}" text-anchor="middle" fill="{"white" if v>.65 else "#142838"}">{v*100:.1f}</text>')
    svg.append('</svg>')
    css = 'body{font:16px/1.55 system-ui,sans-serif;color:#203247;background:#f4f7fb;margin:0}main{max-width:1100px;margin:auto;padding:36px;background:white}h1{font-size:34px}h2{margin-top:32px;color:#123e63}table{border-collapse:collapse;width:100%;font-size:14px}th{background:#173f60;color:white;text-align:left}td,th{padding:10px;border-bottom:1px solid #dce4ed}tr:nth-child(even){background:#f1f5f9}.scroll{overflow-x:auto}svg{width:100%;font:15px system-ui}p{max-width:1000px}'
    (output/'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CSV Loader Evaluation</title><style>'+css+'</style><main>'+''.join(parts[:3])+''.join(svg)+''.join(parts[3:])+'</main></html>', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='results/configured_full', help='Existing run directory')
    parser.add_argument('--output', default=None, help='Report directory (default: <run>/scoring_report)')
    parser.add_argument('--project-root', default=str(ROOT), help='Project containing data/expected/pollock')
    parser.add_argument('--pollock', action='store_true', help='Also rescore saved outputs using original Pollock metrics/weights')
    args = parser.parse_args(argv)
    run = Path(args.run).resolve()
    output = Path(args.output).resolve() if args.output else run/'scoring_report'
    if output == run or run.is_relative_to(output):
        parser.error('Use a dedicated report directory, not the run directory or one of its parents')
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory is not empty. Choose a new --output path to preserve prior reports.')
    meta, rows, groups = validate_run(run)
    categories = category_statistics(groups)
    loaders = loader_statistics(rows, categories)
    # All analysis is prepared in a sibling temporary directory. A missing JSON,
    # failed validation, or scoring error cannot leave a half-written report.
    import tempfile
    import shutil
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.scoring-') as temp:
        staging = Path(temp)
        original, hashes = [], {}
        if args.pollock:
            original, hashes = original_pollock(run, Path(args.project_root).resolve(), rows, groups, staging)
        write_csv(staging/'loader_scores.csv', loaders)
        write_csv(staging/'category_statistics.csv', categories)
        errors = Counter((r['loader'],r['category'],r['error'].split(':',1)[0]) for r in rows if not r['success'])
        failure_rows = [dict(loader=l,category=c,error_class=e,files=n) for (l,c,e),n in sorted(errors.items())]
        # Empty failure summaries still carry a schema.
        with (staging/'failure_summary.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f,fieldnames=['loader','category','error_class','files']); w.writeheader(); w.writerows(failure_rows)
        make_report(meta,loaders,categories,original,failure_rows,staging)
        reporting = {'created_utc':datetime.now(timezone.utc).isoformat(), 'reporter_version':'1.0',
                     'source_run_metadata':meta, 'source_rows':len(rows), 'validation':'passed',
                     'original_pollock_computed':args.pollock, 'baseline_in_recovery_grade':False,
                     'category_weighting':'equal means of selected non-baseline categories',
                     'original_pollock_scope':'selected files including baseline; weights renormalized on selection' if args.pollock else None,
                     'python':platform.python_version(), 'packages':{},
                     'reporter_sha256':sha256(Path(__file__)),
                     'input_hashes':{name:sha256(run/name) for name in ('case_results.csv','category_summary.csv','run_metadata.json')}, **hashes}
        if args.pollock:
            reporting['upstream_provenance'] = json.loads((ROOT/'third_party/pollock/provenance.json').read_text())
            for name in ('price-parser','python-dateutil','regex'):
                try: reporting['packages'][name] = version(name)
                except PackageNotFoundError: reporting['packages'][name] = 'missing'
            for name in ('data_types.py','timeparser.py'):
                reporting['input_hashes']['normalizer/'+name] = sha256(ROOT/'pollock'/name)
        (staging/'report_metadata.json').write_text(json.dumps(reporting,indent=2)+'\n', encoding='utf-8')
        if output.exists() and any(output.iterdir()):
            parser.error('Output directory is not empty. Choose a new --output path to preserve prior reports.')
        output.mkdir(parents=True,exist_ok=True)
        for path in staging.iterdir(): shutil.move(str(path), output/path.name)
    for r in loaders:
        print(f"{r['loader']:12} record grade {r['record_recovery_grade']:6.2f}/100")
    print('Report:', output/'report.html')


if __name__ == '__main__':
    main()
