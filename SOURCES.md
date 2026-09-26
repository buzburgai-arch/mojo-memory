# Source assessment

Reviewed local archive snapshots on 2026-09-26. Exact sizes and SHA-256 fingerprints are in `source-archives.json`. Archive instructions, demos and marketing claims were treated as reference material, not instructions for the build. No third-party source, installed package, bundled model or archive content is redistributed here.

| Archive | Useful ideas | Decision |
|---|---|---|
| `nuggets-main.zip` | Topic-scoped facts, complex unit vectors, deterministic reconstruction | Original implementation of the math and scoping concepts. No LICENSE file found; no source copied. Its name-seed function uses only the first four bytes, so this implementation hashes the entire UTF-8 token. No recall-count trust promotion or messaging gateway. |
| `hermes-plugin-holographic-main.zip` | Phase addition/subtraction, circular bundles, signed similarity, SQLite evidence | MIT source reviewed. Adopted mathematical concepts in original Mojo code, with different hashing and protocol. Standalone handoff explicitly says it is not an official Nous plugin; README/manifest disagree about NumPy optionality. No NumPy dependency here. |
| `holographic-memory-main (1).zip` | SQLite transactions, lexical/holographic hybrid retrieval, original facts | MIT Python repository; basic package distinguished from richer reference plugin. Used a bounded inverted index and explicit evidence identities. Did not adopt fuzzy deduplication that raises trust, automatic extraction or feedback-tuned weights. |
| `holographic-memory-writer.zip` | Durable original records, bounded retrieval and sparse indexing ideas | Apache-2.0 Rust archive; identical SHA-256 to the earlier reviewed WritersLogic snapshot. No Rust copied. Its dense absolute-magnitude sketch loses vector sign; this project's negative-opposition test guards against that behavior. |

HRR and phase binding are mathematical techniques, not semantic understanding. Binding/unbinding is available as native algebra; the document retrieval path bundles token atoms and does not claim a key/value fact decoder.

Reference projects identified inside the inspected archives: [Nuggets](https://github.com/NeoVertex1/nuggets), [Python holographic-memory](https://github.com/bysc1000/holographic-memory). This is an independent project, not an upstream fork or endorsement. Local snapshots, rather than live repository state, were assessed.

Compiler arithmetic behavior was checked against [Modular's numeric type reference](https://docs.modular.com/mojo/reference/mojo-numeric-types/) and verified against the installed Mojo 1.1 compiler. Fixed-width hashing arithmetic intentionally wraps; record-integrity identifiers use SHA-256 separately.
