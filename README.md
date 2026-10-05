# Pollock CSV Loader Benchmark

A Python-driven adaptation of [Pollock](https://github.com/HPI-Information-Systems/Pollock) for comparing Python csv, Pandas, CleverCSV, SQLite, and MySQL. No Docker is required. SQLite uses its native command-line importer; MySQL runs as a separately installed local server.

Current scope: one source dataset, ten isolated pollution categories, configured loading, and header/record/cell evaluation. Combined pollutions and additional datasets are future work. This is an extension project, not a reproduction of the paper's published rankings.

## Requirements

- Python 3.13 (the original project run used 3.13.2).
- VS Code with the Python extension, or another editor.
- MySQL Server installed and running locally, with credentials for your own installation.
- SQLite command-line tools containing `sqlite3.exe`.
- Git for publishing or cloning the repository.

Each teammate installs their own environment and uses their own MySQL credentials. You do not need a shared database account or server. The project always uses a database named `pollock_benchmark`.

## Setup on Windows / VS Code

Open the project root in VS Code. Run the following in its PowerShell terminal:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use the environment's Python directly, for example `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Use that executable in place of `python` in later commands too. In VS Code, run **Python: Select Interpreter** and select `.venv\Scripts\python.exe`.

`requirements.txt` preserves the uploaded environment's pinned versions and is encoded as UTF-8. `requirements-benchmark.txt` provides an unpinned alternative if a pinned distribution is unavailable. Record your installed versions when comparing results; changing versions may change behavior.

### SQLite

Download the Windows command-line tools from [sqlite.org/download.html](https://sqlite.org/download.html). Extract `sqlite3.exe` into `tools/sqlite/` beneath the project root. Do not commit the executable.

```powershell
.\tools\sqlite\sqlite3.exe --version
```

The optional clean baseline script requires this exact location. Configured benchmark adapters also accept `SQLITE_EXE` or a `sqlite3` executable on PATH. Python's built-in `sqlite3` module alone cannot perform our native shell import.

### MySQL

Install [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) and start its local service. Edit `.env` with your local account and password. The example uses `root` for one-time local setup. Don't commit `.env` or you'll leak your passwords.

```powershell
python check_setup.py
python setup_mysql.py
```

`check_setup.py` checks package imports and the MySQL connection. Its printed SQLite version belongs to Python's SQLite library, not necessarily the shell you installed.

`setup_mysql.py` creates `pollock_benchmark` and executes `SET GLOBAL local_infile = ON`. This step requires an administrative account and changes the local server setting. If MySQL restarts, rerun setup if local imports become disabled. Subsequent loading requires access to the database, temporary table creation, and data loading/retrieval. The connector enables `allow_local_infile=True` on its connections.

## Run the project

Run commands from the project root. The supplied fixture is already included at `data/clean/source.csv`. Keep its content and newlines intact.

### 1. Optional clean baseline

```powershell
python run_baseline.py
```

All five loaders should report matching headers and records: nine columns and 83 data records. This script catches errors and continues, so read the output; exiting normally alone does not prove every loader passed. It uses `loaders/`, which contains clean-file adapters.

### 2. Generate and verify Pollock files

```powershell
python generate_pollutions.py
python verify_pollutions.py
```

For the included source, generation produces **2,290 artifact sets**, including the clean baseline. Each contains a polluted CSV, expected CSV, and loading-parameter JSON. Verification checks artifact completeness and representative fixture properties. Do not run verification with Python's `-O` flag because its assertions would be disabled.

Generation overwrites its named artifacts but does not remove unrelated files. The manifest determines which generated cases are used. Current generation and verification include assumptions specific to this fixture; replacing it with a new dataset requires reviewing those assumptions.

### 3. Configured smoke test

```powershell
python run_benchmark.py --smoke --output results/configured_smoke
```

This selects one case per pollution category plus the baseline: **11 files, 55 loader/file results**. Every selected loader must first pass an exact clean baseline comparison. Resolve baseline errors before interpreting pollution results.

### 4. Full configured benchmark

```powershell
python run_benchmark.py --output results/configured_full
```

The full selection contains **2,175 files and 10,875 loader/file results**. It includes all positional variants for the selected separator and quote mutations.

You can run a subset without a MySQL server or SQLite shell:

```powershell
python run_benchmark.py --loaders python_csv pandas clevercsv --smoke --output results/python_smoke
python run_benchmark.py --category extra_record_separator --output results/extra_separator
```

Use a distinct output directory for different selections. Reports are rewritten when an output directory is reused, but older per-file outputs outside the new selection may remain. Compare only files listed in the current `case_results.csv`.

## Selected pollution categories

| Category | Files per loader | Meaning |
| --- | ---: | --- |
| `baseline` | 1 | Clean reference |
| `missing_header` | 1 | Header removed |
| `two_row_header` | 1 | Header expanded to two rows |
| `preamble` | 1 | Preamble before the table |
| `extra_record_separator` | 747 | Extra field separator in a data record |
| `missing_record_separator` | 664 | Missing field separator in a data record |
| `extra_unescaped_quote` | 756 | Extra quote at a header or data position |
| `semicolon_delimiter` | 1 | Semicolon-separated fields |
| `tab_delimiter` | 1 | Tab-separated fields |
| `single_quote_character` | 1 | Single-quote enclosure |
| `backslash_escape` | 1 | Backslash escape character |

The two category identifiers ending in `record_separator` refer to field separators within records, not line terminators. Ten pollution categories plus baseline produce eleven category labels.

## Read the results

Each configured run writes:

| Path within the run directory | Contents |
| --- | --- |
| `case_results.csv` | One row per loader/file: status, exact match, scores, time, errors, diagnostic line count |
| `category_summary.csv` | One row per loader/category: case count, success rate, exact-match rate, mean time and mean scores |
| `run_metadata.json` | Python/platform, selected loaders, file count, smoke flag, selected package versions |
| `outputs/<loader>/<filename>.json` | Parsed header/records, errors, diagnostics and parameters |
| `outputs/<loader>/<filename>` | Convenience CSV export for successful loads |

For example, `outputs/mysql/source.csv.json` preserves SQL `null` values. The CSV export cannot distinguish SQL NULL from an empty string, so use JSON when investigating discrepancies.

### Evaluation definitions

- **Success:** the adapter returned without an exception. Warnings, truncated fields, incorrect headers, or malformed data can still accompany success.
- **Exact match:** raw parsed header and ordered records equal the expected header and records. No normalization is applied here.
- **Precision:** matched items divided by returned items.
- **Recall:** matched items divided by expected items.
- **F1:** harmonic mean of precision and recall.

F1 uses Pollock's cell normalization and duplicate-aware multiset matching. Header scores compare normalized header values. Record scores compare complete tuples: field order and boundaries matter, but record order is ignored. Cell scores compare data values without positions; headers are excluded. Therefore cell F1 can stay high even when columns shift. Exact match catches ordering and raw-value differences that normalized F1 may miss.

Duplicate values count up to their expected multiplicity. SQL NULL remains distinct from an empty string. Both empty expected and returned groups score 1; other zero-denominator cases score 0. A failed load receives zero for all scores, including header scores.

Category summaries average per-file scores, including failures as zero. Rates use the number of files in that category as their denominator. `diagnostic_count` counts captured text lines, not a standardized number of database warnings. MySQL's returned warning list may be limited by its server settings.

`adapter_seconds` includes database connection, import, and retrieval where applicable. It excludes scoring and output writing. A single measurement is not a rigorous throughput comparison.

### Interpret comparisons carefully

Compare loaders within a category. Do not use a pooled average across all files as a balanced ranking: three categories account for nearly all positional variants. Seven categories have one case each, and all cases derive from one dataset. These are descriptive results, not independent samples supporting broad statistical claims.

Configured adapters receive dialect/header/preamble/column-count metadata, but not expected cell values. We are measuring recovery with supplied configuration, not automatic dialect detection. SQLite's importer has fixed quoting conventions. Our non-Pandas configured adapters treat only the first header row as the header; the extra header row remains in data. This is an adapter limitation, not a statement that the underlying libraries cannot handle multirow headers.

These metrics are Pollock-inspired and differ from upstream scoring. We do not compute the paper's simple or weighted aggregate Pollock score. See `README-benchmark.md` for more background.

## Code map

| File or directory | Responsibility |
| --- | --- |
| `generate_pollutions.py` | Creates independent variants and their manifest |
| `verify_pollutions.py` | Checks generated artifacts and fixture properties |
| `pollock/` | Adapted upstream pollution and normalization implementation |
| `benchmark/cases.py` | Selects ten categories from the manifest |
| `benchmark/adapters.py` | Configured loading with each system's own parser |
| `benchmark/evaluation.py` | Normalized precision/recall/F1 |
| `run_benchmark.py` | Baseline preflight, loading, diagnostics, evaluation and reports |
| `loaders/`, `run_baseline.py` | Earlier clean-file sanity checks |
| `check_setup.py`, `setup_mysql.py` | Local dependency and database setup |
| `data/clean/source.csv` | Included source fixture |

SQLite and MySQL parse the input themselves. Python reads back already imported database rows; it does not parse CSV on their behalf. Expected files are used by evaluation after loading.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing Python module | Select the project interpreter and install dependencies into that environment |
| MySQL connection refused | Start the local service and check host/port |
| MySQL access denied | Check your own username/password and database privileges |
| Local file loading disabled | Rerun administrative setup after server restart |
| SQLite executable missing | Extract `sqlite3.exe` to `tools/sqlite/` |
| Missing manifest or parameter file | Run generation followed by verification |
| Pandas ParserError on a polluted case | Inspect the case; malformed fields can legitimately trigger an error |
| Load succeeds but exact match is false | Inspect JSON data and diagnostics; success measures completion only |

## Prepare and publish to GitHub

The sharing package excludes local credentials, environments, generated data/results, and SQLite binaries. `.gitignore` keeps those out of new commits. The source fixture is retained and `.gitattributes` prevents Git from changing its line endings.

1. Create an empty GitHub repository. Do not initialize it with a README if you use the commands below.
2. From the prepared project root, run:

```powershell
git init
git add .
git status --short
git diff --cached --stat
git commit -m "Add configured Pollock benchmark and setup documentation"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your repository URL. Review the staged file list before committing. If the directory is already a Git repository, inspect its existing status and remote rather than rerunning initialization blindly. Ignoring a path does not untrack a file already committed.

Teammates can clone the repository and follow Setup, then generate their own artifacts. To share experiment results later, select compact summary files deliberately instead of committing the entire generated output tree.

## Attribution and project status

Upstream: [Pollock repository](https://github.com/HPI-Information-Systems/Pollock). Paper: [Pollock: A Data Loading Benchmark](https://www.vldb.org/pvldb/vol16/p1870-vitagliano.pdf).

See `THIRD_PARTY_NOTICES.md` and `LICENSE-POLLOCK` for upstream attribution and its MIT notice. A license for the team's original contributions has not been selected here. The upstream code in this package is adapted for this project; do not replace it with a fresh upstream package without checking compatibility.

The original Windows/Python 3.13 run completed all 10,875 results with matching clean baselines. This documentation/comment pass preserves Python behavior. Future development can add clearer evaluation reports, controlled pollution pairs, and additional source datasets.
