# mojo-memory

Local evidence memory with a native Mojo phase-vector core. Keep original records, retrieve a bounded set of relevant historical notes, and return them as advice. Built for repair harnesses and local agents.

The core is real Mojo: deterministic full-UTF-8 token hashing, phase atoms, circular bundling, binding/unbinding, signed cosine similarity, and hybrid scoring. A Python standard-library bridge handles Unicode tokenization, SQLite, JSON and command-line transport. This is a hybrid implementation, not an all-Mojo database. No NumPy, model, embedding API or GPU runtime is required.

## Build and use

Requires Mojo **1.1.0**, Python **3.11+** with its shared library, SQLite and Bash. Tested with Mojo `1.1.0 (8189361e)`, Ubuntu/WSL x86-64 and Python 3.12.3. Windows uses WSL2; a native Windows Mojo binary is not supplied. Rebuild on the target system. The CPU implementation has no GPU-vendor dependency: AMD, NVIDIA or Intel accelerators can coexist with it, but no accelerator paths or cross-device speed claims are included.

```bash
MOJO_BIN=/path/to/mojo bash scripts/build.sh
python3 -m unittest -v test_memory
python3 memory.py --database /absolute/path/memory.db --scope myrepo/train put "Summation counts values with sum, not len."
python3 memory.py --database /absolute/path/memory.db --scope myrepo/train search "sum values"
python3 memory.py --database /absolute/path/memory.db --scope myrepo/train stats
```

`get ID` returns the complete original record and evidence. `delete ID` removes a record and its search terms in the selected scope. `put TEXT --evidence evidence.json` associates a JSON evidence object. On Windows run the same `python memory.py` commands with Windows absolute database paths; use `--distro` for a WSL distribution other than Ubuntu. Build in WSL first.

The CLI starts a worker for each invocation. For low-latency repeated calls, launch `bash scripts/agent.sh DATABASE [--read-only]` and keep its JSON-lines session open. The repair harness uses this persistent mode. Opening a writable session creates an empty database; read-only mode requires an existing database and blocks SQL mutations.

## Protocol

One bounded UTF-8 object per line, with a correlated response:

```json
{"schema_version":1,"request_id":"example","operation":"memory.search","params":{"scope":"myrepo/train","query":"sum values","limit":3}}
```

Operations and exact parameter fields:

| Operation | Parameters |
|---|---|
| `memory.put` | `scope`, `text`, `evidence` (object) |
| `memory.search` | `scope`, `query`, `limit` (1–5) |
| `memory.get` | `scope`, `id` |
| `memory.delete` | `scope`, `id` |
| `memory.stats` | `scope` |

Success returns `{schema_version:1, request_id, status:"ok", result:{...}}`; errors return `status:"error"` and an error object. Bad JSON is rejected without a mutation; oversized/incomplete frames terminate the session. No sockets, arbitrary shell tools or model writes are exposed by this protocol.

## Retrieval and bounds

- Lowercase Unicode terms are deduplicated in encounter order; only the first **64 distinct terms** are indexed/encoded. No stemming or learned semantic embeddings. Choose concise records.
- The scope-filtered inverted index selects at most **64 candidates** by shared-term count, with stable ID ties. It cannot find paraphrases that share no indexed terms. The candidate pool is approximate relative to the full corpus.
- Native Mojo reranks with `0.7 × token Jaccard + 0.3 × max(0, phase similarity)`. The signed raw similarity is retained; opposite phases score near **−1**, not +1. Scores are ranking signals, not confidence.
- **512 dimensions**, Float64 computation, **2048 bytes** per stored Float32 vector. Native atoms use FNV-1a over every UTF-8 byte followed by SplitMix64 phase generation. Encoding ID is `phase-fnv1a-splitmix64-v1-d512`; no compatibility with upstream vector files is claimed.
- **10,000 records per database**; 8 KiB text and 8 KiB JSON evidence per record; 32 KiB request frame; 512-byte query; at most 5 returned hits. Search excerpts are at most 1200 UTF-8 bytes; `get` retains exact text. Capacity errors require explicit deletion, never silent eviction.
- Original content, evidence identity and vector checksums are validated when retrieved. Identity includes scope, text and evidence. Exact repeated puts are idempotent; distinct evidence remains distinct. SQLite WAL transactions serialize writes with a 2-second lock timeout.
- Memory records are always `advisory_only`. A caller's `verified` field is only a historical claim. Hashes detect accidental changes; they do not authenticate a malicious database owner. Scope is a namespace, not multi-user access control. Use local trusted storage; do not treat cloud-sync or network shares as a multi-host database.

## Repair harness integration

The companion `Github Gemini` harness accepts `repair --memory-config PATH`. Configuration:

```json
{"root":"/absolute/path/mojo-memory","database":"/absolute/path/memory.db","scope":"myrepo/train","write":false}
```

Use Windows absolute paths and optional `"distro":"Ubuntu"` for a Windows host. The model can request bounded `repair.recall`; it cannot choose another scope or write records. `write:true` allows the controller to save a hash-checked nonempty patch excerpt only after native verified export. Memory failure leaves the repair result intact. Retrieved notes cannot replace current source reads or native verification.

Use separate databases/scopes for training, validation and test. Freeze the retrieval corpus for measured evaluation; read-only mode prevents new writes but does not clean pre-existing solution leakage. A relevant note is not evidence that a new task is solved.

## Validation and limitations

`scripts/build.sh` compiles the worker and executes native algebra checks. `test_memory.py` uses the compiled worker for persistence, scope isolation, read-only enforcement, deterministic retrieval, corruption checks, bounds and a scalar encoding oracle. `benchmark.py` measures a warm persistent worker on 256 synthetic records and 100 searches; it includes SQLite, native scoring and Python interop. It is not a model-throughput or semantic-quality benchmark. See [verification.md](verification.md) for measured results.

No automatic fact extraction, confidence promotion, message gateways, entity graph, remote service, ANN index or hidden fallback is included. Original records and vectors both consume storage; this is not lossless model-weight compression or an inference engine. Real-model repair improvement, Omarchy and physical AMD/NVIDIA/Intel hardware combinations remain unmeasured.

Reviewed sources and licensing decisions are in [SOURCES.md](SOURCES.md), with exact archive hashes in [source-archives.json](source-archives.json). Original code is MIT licensed.
