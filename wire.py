"""Bounded stdlib I/O and persistence for the native Mojo memory worker."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DIM = 512
MAX_FRAME = 32768
MAX_RECORDS = 10000
ENCODING = "phase-fnv1a-splitmix64-v1-d512"
SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE memories (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL, text TEXT NOT NULL,
 evidence TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 vector BLOB NOT NULL, vector_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX scoped_memories ON memories(scope, id);
CREATE TABLE terms (
 scope TEXT NOT NULL, term TEXT NOT NULL, id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
 PRIMARY KEY(scope, term, id)
) WITHOUT ROWID;
"""
connection: sqlite3.Connection


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def checked_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"{name} must be nonempty text without NUL")
    if len(value.encode("utf-8")) > maximum:
        raise ValueError(f"{name} exceeds {maximum} bytes")
    return value


def checked_int(value: object, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer between 1 and {maximum}")
    return value


def tokenize(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[^\W_]+(?:_[^\W_]+)*", text.casefold())))[:64]


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON value: {value}")


def open_store(path: str, read_only: bool = False) -> None:
    global connection
    target = Path(path).resolve()
    if read_only:
        connection = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, timeout=2)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(target, timeout=2)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    if not read_only:
        connection.execute("PRAGMA journal_mode=WAL")
        # Serialize first creation; reject unrelated/unknown databases instead of modifying them.
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not tables:
                for statement in SCHEMA.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.executemany(
                    "INSERT INTO metadata VALUES (?,?)", [("schema", "1"), ("encoding", ENCODING)]
                )
            validate_store()
            connection.commit()
        except Exception:
            connection.rollback()
            connection.close()
            raise
    else:
        validate_store()


def validate_store() -> None:
    metadata = dict(connection.execute("SELECT key,value FROM metadata"))
    if metadata != {"schema": "1", "encoding": ENCODING}:
        raise ValueError("Unsupported memory schema or encoding")


def close_store() -> None:
    connection.close()


def read() -> SimpleNamespace:
    while True:
        frame = sys.stdin.buffer.readline(MAX_FRAME + 1)
        if not frame:
            return SimpleNamespace(is_eof=True)
        request_id: str | None = None
        try:
            if len(frame) > MAX_FRAME or not frame.endswith(b"\n"):
                # Closing, rather than consuming attacker-controlled unbounded continuation.
                raise SystemExit("Oversized or incomplete memory frame")
            data = json.loads(frame, object_pairs_hook=unique, parse_constant=reject_constant)
            if not isinstance(data, dict):
                raise ValueError("Request must be an object")
            request_id = checked_text(data.get("request_id"), "request_id", 64)
            if (
                set(data) != {"schema_version", "request_id", "operation", "params"}
                or type(data["schema_version"]) is not int
                or data["schema_version"] != 1
            ):
                raise ValueError("Invalid request envelope")
            operation = data["operation"]
            fields = {
                "memory.put": {"scope", "text", "evidence"},
                "memory.search": {"scope", "query", "limit"},
                "memory.get": {"scope", "id"},
                "memory.delete": {"scope", "id"},
                "memory.stats": {"scope"},
            }
            if not isinstance(operation, str) or operation not in fields:
                raise ValueError("Unknown operation")
            params = data["params"]
            if not isinstance(params, dict) or set(params) != fields[operation]:
                raise ValueError("Invalid operation fields")
            scope = checked_text(params["scope"], "scope", 160)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", scope):
                raise ValueError("Invalid scope")
            tokens: list[str] = []
            if operation == "memory.put":
                body = checked_text(params["text"], "text", 8192)
                evidence = params["evidence"]
                if not isinstance(evidence, dict) or len(canonical(evidence).encode()) > 8192:
                    raise ValueError("Evidence must be an object of at most 8192 bytes")
                tokens = tokenize(body)
                if not tokens:
                    raise ValueError("Record has no searchable tokens")
            elif operation == "memory.search":
                tokens = tokenize(checked_text(params["query"], "query", 512))
                checked_int(params["limit"], "limit", 5)
            elif operation in {"memory.get", "memory.delete"}:
                if not re.fullmatch(r"[a-f0-9]{64}", checked_text(params["id"], "id", 64)):
                    raise ValueError("Invalid memory ID")
            return SimpleNamespace(
                is_eof=False, request_id=request_id, operation=operation, params=params, tokens=tokens
            )
        except (ValueError, TypeError, RecursionError) as error:
            failure(SimpleNamespace(request_id=request_id), str(error))


def respond(command: SimpleNamespace, result: dict[str, object]) -> None:
    print(
        canonical({"schema_version": 1, "request_id": command.request_id, "status": "ok", "result": result}),
        flush=True,
    )


def failure(command: SimpleNamespace, error: str) -> None:
    print(
        canonical(
            {
                "schema_version": 1,
                "request_id": command.request_id,
                "status": "error",
                "error": {"code": "MEMORY_ERROR", "message": str(error)[:512]},
            }
        ),
        flush=True,
    )


def put(command: SimpleNamespace, vector: list[float]) -> None:
    params = command.params
    content_hash = hashlib.sha256(params["text"].encode()).hexdigest()
    identity = hashlib.sha256(canonical(params).encode()).hexdigest()
    blob = struct.pack(f"<{DIM}f", *vector)
    connection.execute("BEGIN IMMEDIATE")
    try:
        exists = connection.execute("SELECT 1 FROM memories WHERE id=?", (identity,)).fetchone()
        if not exists:
            if connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0] >= MAX_RECORDS:
                raise ValueError("Memory capacity reached; explicitly delete obsolete records")
            connection.execute(
                "INSERT INTO memories(id,scope,text,evidence,content_sha256,vector,vector_sha256) VALUES (?,?,?,?,?,?,?)",
                (
                    identity,
                    params["scope"],
                    params["text"],
                    canonical(params["evidence"]),
                    content_hash,
                    blob,
                    hashlib.sha256(blob).hexdigest(),
                ),
            )
            connection.executemany(
                "INSERT INTO terms VALUES (?,?,?)",
                [(params["scope"], term, identity) for term in command.tokens],
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    respond(command, {"id": identity, "inserted": not bool(exists), "content_sha256": content_hash})


def candidates(command: SimpleNamespace) -> list[dict[str, Any]]:
    terms = command.tokens
    if not terms:
        return []
    placeholders = ",".join("?" for _ in terms)
    rows = connection.execute(
        f"SELECT m.*,COUNT(*) AS overlap FROM terms t JOIN memories m ON m.id=t.id WHERE t.scope=? AND m.scope=? AND t.term IN ({placeholders}) GROUP BY m.id ORDER BY overlap DESC,m.id LIMIT 64",
        (command.params["scope"], command.params["scope"], *terms),
    ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        candidate = dict(row)
        validate_record(candidate)
        vector = struct.unpack(f"<{DIM}f", candidate["vector"])
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Corrupt vector")
        candidate["vector"] = vector
        token_count = len(tokenize(candidate["text"]))
        candidate["lexical"] = candidate["overlap"] / (len(terms) + token_count - candidate["overlap"])
        results.append(candidate)
    return results


def validate_record(row: dict[str, Any]) -> None:
    if hashlib.sha256(row["vector"]).hexdigest() != row["vector_sha256"]:
        raise ValueError("Memory vector hash mismatch")
    if hashlib.sha256(row["text"].encode()).hexdigest() != row["content_sha256"]:
        raise ValueError("Memory content hash mismatch")
    params = {"scope": row["scope"], "text": row["text"], "evidence": json.loads(row["evidence"])}
    if hashlib.sha256(canonical(params).encode()).hexdigest() != row["id"]:
        raise ValueError("Memory evidence hash mismatch")


def public_record(row: dict[str, Any], *, excerpt: bool = False) -> dict[str, object]:
    body = row["text"]
    if excerpt:
        body = body.encode()[:1200].decode("utf-8", errors="ignore")
    return {
        "id": row["id"],
        "scope": row["scope"],
        "text": body,
        "truncated": body != row["text"],
        "content_sha256": row["content_sha256"],
        "evidence": json.loads(row["evidence"]) if not excerpt else {"available_via": "memory.get"},
        "created_at": row["created_at"],
        "advisory_only": True,
    }


def search_result(
    command: SimpleNamespace, rows: list[dict[str, Any]], scores: list[tuple[float, float]]
) -> None:
    ordered = sorted(zip(rows, scores, strict=True), key=lambda pair: (-pair[1][0], pair[0]["id"]))
    hits = [
        public_record(row, excerpt=True) | {"score": score, "holographic_similarity": hrr}
        for row, (score, hrr) in ordered[: command.params["limit"]]
    ]
    respond(
        command,
        {
            "hits": hits,
            "candidates": len(rows),
            "candidate_limit": 64,
            "advisory_only": True,
            "encoding": ENCODING,
        },
    )


def other(command: SimpleNamespace) -> None:
    params = command.params
    if command.operation == "memory.stats":
        count = connection.execute(
            "SELECT COUNT(*) FROM memories WHERE scope=?", (params["scope"],)
        ).fetchone()[0]
        respond(command, {"records": count, "encoding": ENCODING, "dimension": DIM, "capacity": MAX_RECORDS})
    elif command.operation == "memory.get":
        row = connection.execute(
            "SELECT * FROM memories WHERE scope=? AND id=?", (params["scope"], params["id"])
        ).fetchone()
        if row:
            validate_record(dict(row))
        respond(command, {"memory": public_record(dict(row)) if row else None, "advisory_only": True})
    else:
        with connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE scope=? AND id=?", (params["scope"], params["id"])
            )
        respond(command, {"deleted": cursor.rowcount == 1})
