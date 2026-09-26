from std.collections import List
from std.python import Python, PythonObject
from std.sys import argv
from core import DIM, Phases, encode, hybrid_score, similarity


def tokens_from(value: PythonObject) raises -> List[String]:
    var tokens = List[String]()
    for i in range(len(value)):
        tokens.append(String(value[i]))
    return tokens^


def main() raises:
    Python.add_to_path(".")
    var wire = Python.import_module("wire")
    var args = argv()
    if len(args) != 2 and len(args) != 3:
        raise Error("usage: mojo-memory DATABASE [--read-only]")
    var read_only = len(args) == 3
    if read_only and args[2] != "--read-only":
        raise Error("unknown option")
    wire.open_store(args[1], read_only)
    while True:
        var command = wire.read()
        if Bool(py=command.is_eof):
            break
        try:
            var operation = String(command.operation)
            if operation == "memory.put":
                var vector = encode(tokens_from(command.tokens))
                var values = Python.list()
                for i in range(DIM):
                    values.append(vector.values[i])
                wire.put(command, values)
            elif operation == "memory.search":
                var query = encode(tokens_from(command.tokens))
                var candidates = wire.candidates(command)
                var scores = Python.list()
                for i in range(len(candidates)):
                    var values = List[Float64](capacity=DIM)
                    for j in range(DIM):
                        values.append(Float64(py=candidates[i]["vector"][j]))
                    var hrr = similarity(query, Phases(values^))
                    var score = hybrid_score(Float64(py=candidates[i]["lexical"]), hrr)
                    scores.append(Python.tuple(score, hrr))
                wire.search_result(command, candidates, scores)
            else:
                wire.other(command)
        except error:
            wire.failure(command, String(error))
    wire.close_store()
