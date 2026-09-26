"""Reproducible warm-worker latency fixture; not semantic or model-quality evidence."""

import json
import platform
import statistics
import tempfile
import time
from pathlib import Path

from test_memory import Worker


def main():
    with tempfile.TemporaryDirectory() as directory:
        worker = Worker(Path(directory) / "benchmark.db")
        try:
            inserts = []
            for index in range(256):
                start = time.perf_counter()
                result = worker.call(
                    "put",
                    {
                        "scope": "benchmark/train",
                        "text": f"repair sum values issue {index} inspect arithmetic regression",
                        "evidence": {"synthetic": True},
                    },
                )
                assert result["status"] == "ok", result
                inserts.append(1000 * (time.perf_counter() - start))
            latency = []
            for _ in range(100):
                start = time.perf_counter()
                result = worker.call(
                    "search", {"scope": "benchmark/train", "query": "sum values arithmetic", "limit": 3}
                )
                assert result["status"] == "ok", result
                assert result["result"]["candidates"] == 64
                latency.append(1000 * (time.perf_counter() - start))
            report = {
                "platform": platform.platform(),
                "records": 256,
                "searches": 100,
                "candidate_limit": 64,
                "dimension": 512,
                "insert_warm_median_ms": statistics.median(inserts[1:]),
                "search_median_ms": statistics.median(latency),
                "search_p95_ms": sorted(latency)[94],
                "scope": "synthetic lexical-overlap fixture; no model speed or repair-quality claim",
            }
            print(json.dumps(report, indent=2))
        finally:
            worker.close()


if __name__ == "__main__":
    main()
