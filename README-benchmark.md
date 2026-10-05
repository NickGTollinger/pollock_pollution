# Configured Pollock subset benchmark

Merge these files into your existing pollock-benchmark project. Keep the adapted pollock/ package and the generated data from the prior add-on. Existing baseline loaders and run_baseline.py are unchanged; this runner uses the separate benchmark/adapters.py implementations.

## Run on Windows / PowerShell

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-benchmark.txt
.\.venv\Scripts\python.exe run_benchmark.py --smoke --output results/configured_smoke
.\.venv\Scripts\python.exe run_benchmark.py --output results/configured_full
```

Smoke means 11 inputs: one representative per selected category plus the baseline. It checks plumbing, not all pollution positions. Every configured baseline must match expected content before the runner proceeds. If local imports are disabled after a MySQL restart, run setup_mysql.py again.

You can restrict loaders or categories:

```powershell
.\.venv\Scripts\python.exe run_benchmark.py --loaders python_csv pandas clevercsv --smoke --output results/python_smoke
.\.venv\Scripts\python.exe run_benchmark.py --category extra_record_separator --output results/extra_separator
```

The full selection is 2,175 files, giving 10,875 loader/file runs with all five loaders:

| Category | Files |
|---|---:|
| baseline | 1 |
| missing_header | 1 |
| two_row_header | 1 |
| preamble | 1 |
| extra_record_separator | 747 |
| missing_record_separator | 664 |
| extra_unescaped_quote | 756 |
| semicolon_delimiter | 1 |
| tab_delimiter | 1 |
| single_quote_character | 1 |
| backslash_escape | 1 |

Separator cases use only data rows; quote cases include all header/data cells. Header quote positions are identifiable from row0 in their filenames. Ten categories are not ten physical files. Multiple-pollution cases are a later extension.

## Configuration and limitations

Every adapter receives the generated parameters: encoding, delimiter, quote/escape convention, row delimiter, preamble length, header count and column count. No expected cell values or metadata column_names are supplied to a loader. SQL schemas use the known n_columns from metadata (which may differ by case); this is configured loading, not automatic schema inference.

- Python csv / CleverCSV: use supported dialect settings, skip the configured number of parsed preamble records, recognize zero or one header. Two-row headers use the first header and leave the additional header as a record. This limitation is deliberately scored, not repaired. Python defaults to permissive parsing (strict=False).
- Pandas: C engine defaults, native header=None/0/[0,1], skiprows for preamble, string values, no automatic NA conversion. MultiIndex labels are serialized with spaces into the expected header representation. index_col=False for single/no header prevents accidental index inference; native warnings about lost cells are captured. No bad-line skipping is requested.
- SQLite: native command-line .import into a predefined TEXT table. Field/row separators and preamble skipping are configured. Quote and escape behavior is the fixed SQLite CSV convention; apostrophe/backslash cases expose those limitations. Zero/one header handling as above. The sqlite3 executable defaults to tools/sqlite/sqlite3.exe; SQLITE_EXE can override it or a system sqlite3 is used.
- MySQL: native LOAD DATA LOCAL INFILE into a temporary LONGTEXT table, explicit delimiter/quote/escape/row-separator configuration and preamble skipping. UTF-8 is used for the selected ASCII-compatible inputs. Zero/one header handling as above. No newline guessing or parsing with another loader. SQL NULL remains distinct from an empty string for evaluation. Server local_infile must be enabled.

These adapters are a documented project implementation, not a verified line-for-line recreation of upstream SUT wrappers. Upstream wrapper retrieval was blocked during development. Unsupported multirow-header handling reflects these adapters' capabilities; do not claim a database or CSV library could never support it with a different integration.

## Reports

- case_results.csv: success (completed without an exception), exact match, counts, nine metrics, end-to-end adapter time, diagnostic counts, errors.
- category_summary.csv: per-loader/category averages including failed loads as zeros. Do not use a naive mean over all files as an overall ranking: position-heavy categories dominate it. If needed, average category means excluding baseline and label it an unweighted subset score.
- outputs/<loader>/*.json: authoritative parsed header/records, NULL values, parameters and diagnostics.
- outputs/<loader>/*.csv: convenient export for successful loads; CSV alone cannot distinguish NULL from empty string.
- run_metadata.json: Python/platform/package versions and run selection. Also retain check_setup.py output for database versions and record MySQL sql_mode/configuration when reporting experiments.

A completed load can have corrupt data or warnings. Success is not correctness. Exact match compares original strings and order. F1 tolerates normalized equivalent values and ignores record order while preserving duplicates and cell order within records. Timing includes connection/subprocess/table setup and retrieval, not just parsing; do not label it pure parser throughput.

## Evaluation changes from supplied upstream metrics.py

This evaluator uses conventional precision = matched/actual and recall = matched/expected (the supplied upstream code labels these in reverse). It uses duplicate-aware Counters, tuple record keys to avoid concatenation collisions, header presence metadata to avoid treating the first data row as a header, and normalized values consistently. Cell metrics cover data cells only, since headers have separate metrics; upstream code includes headers and uses raw values for cell metrics. NULL remains separate from empty text. If both expected/actual groups are empty, their metrics are 1; a header-free case therefore has vacuously perfect header metrics, not demonstrated header recognition.

These are Pollock-inspired metrics with documented corrections; results are not directly interchangeable with the original weighted Pollock score. No weighted original score is calculated.

## Validation

Tested on Python 3.12 here; Python 3.13 and native Windows SQLite/MySQL need your local smoke run. The three Python adapters completed the full selected-file run; the final Pandas configuration also completed a full selected-file run. Metric edge checks covered duplicates, conventional precision/recall, record-boundary collisions, no-header records, and NULL/empty distinction. SQLite/MySQL were not executed here because their server/CLI are unavailable.
