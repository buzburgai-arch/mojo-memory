"""One-request CLI for the persistent native service; supports Linux and Windows/WSL."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def native_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name != "nt":
        return value
    if len(value) < 3 or value[1:3] != ":/":
        raise ValueError("Windows requires local drive paths")
    return f"/mnt/{value[0].lower()}/{value[3:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Mojo phase-vector memory with retained evidence")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--scope", required=True, help="Explicit repository/partition namespace")
    parser.add_argument("--distro", default="Ubuntu")
    commands = parser.add_subparsers(dest="operation", required=True)
    put = commands.add_parser("put")
    put.add_argument("text")
    put.add_argument("--evidence", type=Path, help="JSON object, at most 8192 bytes")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=3)
    commands.add_parser("stats")
    for operation in ("get", "delete"):
        commands.add_parser(operation).add_argument("id")
    args = parser.parse_args()
    params: dict[str, object] = {"scope": args.scope}
    try:
        if args.operation == "put":
            evidence: object = {}
            if args.evidence:
                with args.evidence.open("rb") as stream:
                    content = stream.read(8193)
                if len(content) > 8192:
                    raise ValueError("Evidence file exceeds 8192 bytes")
                evidence = json.loads(content)
            params |= {"text": args.text, "evidence": evidence}
        elif args.operation == "search":
            params |= {"query": args.query, "limit": args.limit}
        elif args.operation in {"get", "delete"}:
            params["id"] = args.id
        command = [
            "bash",
            native_path(Path(__file__).parent / "scripts/agent.sh"),
            native_path(args.database),
        ]
        if args.operation not in {"put", "delete"}:
            command.append("--read-only")
        if os.name == "nt":
            command = ["wsl.exe", "-d", args.distro, "--exec"] + command
        request = {
            "schema_version": 1,
            "request_id": uuid.uuid4().hex,
            "operation": "memory." + args.operation,
            "params": params,
        }
        frame = (json.dumps(request, ensure_ascii=False) + "\n").encode()
        if len(frame) > 32768:
            raise ValueError("Request exceeds protocol limit")
        completed = subprocess.run(command, input=frame, capture_output=True, timeout=15)
        if completed.returncode:
            raise RuntimeError(completed.stderr.decode(errors="replace")[:1024])
        result = json.loads(completed.stdout)
        if result.get("request_id") != request["request_id"]:
            raise ValueError("Mismatched reply")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
