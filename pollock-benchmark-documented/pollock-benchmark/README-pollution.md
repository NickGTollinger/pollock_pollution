# Pollock pollution generation add-on

Merge this ZIP's contents into the existing pollock-benchmark folder. It adds the pollock package, generate_pollutions.py, verify_pollutions.py, and requirements-pollution.txt. Existing loaders and credentials are not included or changed.

Run in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-pollution.txt
.\.venv\Scripts\python.exe generate_pollutions.py
.\.venv\Scripts\python.exe verify_pollutions.py
.\.venv\Scripts\python.exe -m pip freeze > requirements.txt
```

Outputs:
- data/polluted/pollock/: files to test
- data/expected/pollock/: corresponding clean expected content
- data/parameters/pollock/: original Pollock loading metadata
- data/pollock_manifest.json: filenames, functions, and arguments

The generator includes every invocation in the supplied original pollute_main.py, including the source baseline. Generation support does not require using every case in the final project; select the agreed subset later through the manifest. No additional custom pollutions are introduced.

Existing generated names are overwritten on reruns; unrelated files are not deleted. The manifest is the authoritative list for a run. Use a separate directory for custom cases.

Adaptations: portable filesystem paths; no shell commands or sut dependency; newline="" in polluted/expected CSV writers; deterministic little-endian date order replacing timeparser's Unix date subprocess; raw regex literals to avoid modern Python escape warnings. Pollution function bodies and expected-content construction remain as supplied.

This stage generates data only. Do not interpret the existing baseline runner as a pollution benchmark yet. Loader settings and header handling must be settled before testing these cases. The included metrics.py is upstream reference code, not integrated evaluation. Dependencies are unpinned to resolve on Python 3.13; freeze your working environment after installation.

Original source: https://github.com/HPI-Information-Systems/Pollock
Reference: Vitagliano et al., Pollock: A Data Loading Benchmark, PVLDB 16(8), 2023.
Retain the original repository LICENSE with your project when redistributing upstream code.
