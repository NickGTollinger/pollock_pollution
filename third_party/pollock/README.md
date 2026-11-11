# Upstream Pollock reference material

Repository: https://github.com/HPI-Information-Systems/Pollock
Revision: bd2a646f4cf55d2bd4e76df511c9c9f675ae7bcc
Retrieved: 2026-11-11

- metrics_reference.py is upstream pollock/metrics.py, unmodified.
- evaluate_reference.py is upstream evaluate.py, unmodified.
- pollock_weights.json and LICENSE are unmodified upstream files.
- provenance.json records source paths and SHA-256 hashes.

Retain the MIT license notice when redistributing these files or derived code.
The production Counter-based port is benchmark/pollock_scoring.py; it preserves
these metrics' conventions and uses the project's adapted normalizer. Reference
scripts are stored for inspection and optional validation, not normal execution.
