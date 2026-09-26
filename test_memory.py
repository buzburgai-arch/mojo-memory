"""End-to-end tests against the compiled worker, with a scalar oracle for its math."""

import hashlib
import json
import math
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Worker:
    def __init__(self, database, readonly=False):
        self.process = subprocess.Popen(
            [str(ROOT / "build/mojo-memory"), str(database)] + (["--read-only"] if readonly else []),
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def call(self, operation, params):
        self.process.stdin.write(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": "test",
                    "operation": "memory." + operation,
                    "params": params,
                }
            )
            + "\n"
        )
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        if not response:
            raise RuntimeError(self.process.stderr.read())
        return json.loads(response)

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)
        self.process.stdout.close()
        self.process.stderr.close()


def oracle_atom(token):
    mask = (1 << 64) - 1
    seed = 14695981039346656037
    for byte in token.encode():
        seed = ((seed ^ byte) * 1099511628211) & mask
    vector = []
    for _ in range(512):
        seed = (seed + 0x9E3779B97F4A7C15) & mask
        mixed = ((seed ^ (seed >> 30)) * 0xBF58476D1CE4E5B9) & mask
        mixed = ((mixed ^ (mixed >> 27)) * 0x94D049BB133111EB) & mask
        mixed ^= mixed >> 31
        vector.append((mixed >> 11) * (2 * math.pi / (1 << 53)))
    return vector


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "memory.db"
        self.worker = Worker(self.db)
        self.addCleanup(self.worker.close)

    def put(self, text="sum values repair", scope="demo/train", evidence=None):
        result = self.worker.call(
            "put", {"scope": scope, "text": text, "evidence": evidence or {"source": "test"}}
        )
        self.assertEqual(result["status"], "ok", result)
        return result["result"]

    def search(self, query="sum", scope="demo/train"):
        return self.worker.call("search", {"scope": scope, "query": query, "limit": 3})["result"]

    def test_native_encoding_matches_independent_scalar_oracle(self):
        self.put("café")
        with sqlite3.connect(self.db) as db:
            blob = db.execute("SELECT vector FROM memories").fetchone()[0]
        actual = struct.unpack("<512f", blob)
        for left, right in zip(actual, oracle_atom("café"), strict=True):
            # One-token bundles wrap into [-pi,pi]. Float32 storage retains phase equivalence.
            self.assertLess(abs(math.cos(left - right) - 1), 1e-12)

    def test_persistence_deduplication_and_scope_isolation(self):
        first = self.put()
        self.assertFalse(self.put()["inserted"])
        self.put(scope="demo/heldout")
        self.assertEqual(len(self.search()["hits"]), 1)
        self.assertEqual(self.search(scope="other/train")["hits"], [])
        other = Worker(self.db, readonly=True)
        try:
            hit = other.call("search", {"scope": "demo/train", "query": "sum", "limit": 1})["result"]["hits"][
                0
            ]
            self.assertEqual(hit["id"], first["id"])
            self.assertTrue(hit["advisory_only"])
            self.assertEqual(
                other.call("delete", {"scope": "demo/train", "id": first["id"]})["status"], "error"
            )
        finally:
            other.close()

    def test_get_evidence_delete_and_no_cross_scope_access(self):
        identity = self.put(evidence={"source_sha256": "a" * 64})["id"]
        self.assertIsNone(self.worker.call("get", {"scope": "other", "id": identity})["result"]["memory"])
        record = self.worker.call("get", {"scope": "demo/train", "id": identity})["result"]["memory"]
        self.assertEqual(record["evidence"]["source_sha256"], "a" * 64)
        self.assertEqual(record["content_sha256"], hashlib.sha256(record["text"].encode()).hexdigest())
        self.assertFalse(self.worker.call("delete", {"scope": "other", "id": identity})["result"]["deleted"])
        self.assertTrue(
            self.worker.call("delete", {"scope": "demo/train", "id": identity})["result"]["deleted"]
        )
        self.assertEqual(self.search()["hits"], [])

    def test_native_ranking_and_unicode(self):
        expected = self.put("sum values")["id"]
        self.put("sum repair unrelated longer content")
        self.assertEqual(self.search("sum values")["hits"][0]["id"], expected)
        self.put("CAFÉ unicode encoding")
        self.assertEqual(len(self.search("café")["hits"]), 1)
        self.assertEqual(self.search("!!!")["hits"], [])

    def test_candidates_bounded_and_stable(self):
        for index in range(70):
            self.put(f"shared issue number {index}")
        first = self.search("shared")
        self.assertEqual(first["candidates"], 64)
        self.assertEqual(first, self.search("shared"))
        self.assertEqual(len(first["hits"]), 3)

    def test_malformed_requests_leave_store_usable(self):
        cases = [
            ("search", {"scope": "s", "query": "sum", "limit": True}),
            ("put", {"scope": "s", "text": "x" * 8193, "evidence": {}}),
            ("put", {"scope": "s", "text": "!!!", "evidence": {}}),
            ("search", {"scope": "bad scope", "query": "sum", "limit": 1}),
            ("search", {"scope": "s", "query": "sum", "limit": 1, "write": True}),
        ]
        for operation, params in cases:
            self.assertEqual(self.worker.call(operation, params)["status"], "error")
        self.put()

    def test_corrupt_evidence_rejected(self):
        self.put()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE memories SET evidence='{}'")
        response = self.worker.call("search", {"scope": "demo/train", "query": "sum", "limit": 1})
        self.assertEqual(response["status"], "error")
        self.assertIn("hash mismatch", response["error"]["message"])

    def test_corrupt_vector_rejected(self):
        self.put()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE memories SET vector=zeroblob(2048)")
        response = self.worker.call("search", {"scope": "demo/train", "query": "sum", "limit": 1})
        self.assertEqual(response["status"], "error")
        self.assertIn("vector hash mismatch", response["error"]["message"])

    def test_long_record_search_is_excerpt_get_is_exact(self):
        text = "sum " + "é" * 3000
        identity = self.put(text)["id"]
        hit = self.search()["hits"][0]
        self.assertTrue(hit["truncated"])
        self.assertLessEqual(len(hit["text"].encode()), 1200)
        record = self.worker.call("get", {"scope": "demo/train", "id": identity})["result"]["memory"]
        self.assertEqual(record["text"], text)


if __name__ == "__main__":
    unittest.main()
