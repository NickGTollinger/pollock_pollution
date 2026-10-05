# Documentation and sharing pass

- Added the main README with Windows/VS Code setup, MySQL and SQLite setup,
  commands, selected categories, evaluation definitions, troubleshooting,
  project structure, and GitHub publishing instructions.
- Added comments explaining configuration translation, duplicate-aware scoring,
  position/order limitations, timing scope, warnings, and baseline-only adapters.
- Added .env.example, expanded .gitignore, and added .gitattributes.
- Converted the existing pinned requirements.txt from UTF-16 to UTF-8 without
  changing dependency versions.
- Added upstream LICENSE-POLLOCK and THIRD_PARTY_NOTICES.md.
- Excluded local .env, virtual environment, generated data/results, caches,
  and SQLite executables from this archive.

Validation: Python AST comparisons confirmed comments did not change executable
code. Compilation passed. On Python 3.12.14, generation and verification
passed for all 2,290 artifact sets; an 11-case smoke run completed for Python csv,
Pandas, and CleverCSV with exact clean baselines. SQLite/MySQL were not rerun
during this pass. The earlier user run checked all five loaders on Python 3.13.

To apply this archive to an existing working project, copy its code/docs into
the project root. Keep your current .env, .venv, tools, generated data, and
results. Do not overwrite your real .env with .env.example. For a fresh checkout,
follow README.md and create .env from the example.
