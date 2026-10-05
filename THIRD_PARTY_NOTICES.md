# Pollock attribution

The adapted `pollock/` package and `data/clean/source.csv` originate from
[HPI Information Systems' Pollock repository](https://github.com/HPI-Information-Systems/Pollock).
The pollution generation schedule in `generate_pollutions.py` derives from its
`pollute_main.py`. Retain `LICENSE-POLLOCK` when distributing these materials.
Its copyright year is reproduced exactly as upstream writes it.

Paper: [Pollock: A Data Loading Benchmark](https://www.vldb.org/pvldb/vol16/p1870-vitagliano.pdf).

Local adaptations include portable directory handling, removal of Unix shell
dependencies, deterministic date-order handling for this fixture, and explicit
newline preservation on Windows. Original pollution operations are retained.
The project provides its own loader adapters and Pollock-inspired evaluation;
these are not a verified reproduction of upstream SUT wrappers or aggregate scores.

The upstream MIT notice applies to upstream-derived material. This package does
not select a license for the team's original contributions; the team can decide
that separately before a public release. SQLite binaries are installed separately.
