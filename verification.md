# Verification — 2026-09-26

The compiled worker passed the native Mojo checks for deterministic atoms, distinction beyond a token's first four bytes, binding inversion, negative similarity for opposite phases, and token bundling. Built using Mojo **1.1.0 (8189361e)**. The installed compiler emitted a nonfatal missing-Crashpad-helper warning.

All **9 standalone Python integration tests** passed against the actual compiled worker. They cover an independent scalar encoding oracle, exact evidence retention, restart persistence, idempotent writes, read-only rejection, cross-scope get/search/delete isolation, Unicode, ranking, bounded candidates, deterministic ties, invalid requests, exact-vs-excerpt retrieval, and evidence/vector corruption. Python bridge and CLI passed strict mypy; lint checks passed. Tests use temporary databases and no external models or services.

The companion repair harness passed **85 unit tests and 11 integration tests** on Windows and Linux/WSL. Its new native integration passes through a scripted HTTP model, actual Mojo memory and actual Triad repair verification: recall → current source read → precise patch → native checks → nonempty export → memory save → read-only restart. Initial verification failed, final verification passed, one record was added, and the held-out scope was not returned. A fake `verified` field in a seeded note did not grant task success. The primary model used three scripted turns.

The synthetic warm-worker benchmark used **256 records**, **100 searches**, **64 candidates per query** and **512 dimensions**:

| Measurement | Result |
|---|---:|
| Warm insertion median | 1.142 ms |
| Recall median | 10.226 ms |
| Recall p95 | 10.656 ms |

Exact environment and results are in `benchmark-result.json`; reproduce with `python3 benchmark.py` after building. These timings include JSON, SQLite, Python interop and Mojo scoring. They exclude model inference and cold process startup. There is no baseline speedup or real-model repair improvement claim. Variation with database size, contention, filesystem and hardware is expected.

Validated platform: Linux x86-64 under WSL2 and a Windows host calling the same WSL worker. Native Windows compilation, Omarchy, GPU execution and physical cross-vendor hardware were not tested. The implementation runs on the CPU without CUDA, ROCm or Intel accelerator dependencies.
