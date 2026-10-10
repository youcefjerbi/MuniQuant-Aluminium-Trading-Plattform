# ADR 0001: Python application with a C++ kernel

Status: accepted for v0.1.

Context: a two-engineer team needs a maintainable evidence workflow and the user requests Python and C++.

Decision: keep API, I/O, transactions and orchestration in Python; use Python Decimal for unit arithmetic and compile only candidate name distance as a C++17 pybind11 extension. Serve a same-origin HTML/CSS/JavaScript interface from FastAPI.

Alternatives: all Python would simplify packaging but would not satisfy the requested native component; a separate C++ service and separate frontend service add deployment and protocol overhead.

Consequences: one deployment and native integration tests; C++ compiler required for source builds. No performance claims without measurement. More native work requires profiling evidence.

Measured evidence, 2026-10-10: seeded 1,000 pairs of 64-character Unicode names produced equal distances. Python 0.294067s, native 0.005005s, 58.75× speedup on this workstation. Raw result: docs/native-benchmark.json. This justifies the ranking kernel; Python retains all unit arithmetic.
