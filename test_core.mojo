from std.collections import List
from std.math import abs
from std.testing import assert_equal, assert_true
from core import DIM, TAU, Phases, atom, bind, unbind, encode, similarity


def main() raises:
    var a = atom("repair.sum")
    var b = atom("repair.len")
    assert_true(abs(similarity(a, atom("repair.sum")) - 1) < 1e-12)
    assert_true(abs(similarity(a, b)) < 0.2)
    assert_true(abs(similarity(unbind(bind(a, b), b), a) - 1) < 1e-12)
    var opposite = List[Float64]()
    for i in range(DIM):
        opposite.append(a.values[i] + TAU / 2)
    assert_true(similarity(a, Phases(opposite^)) < -0.999999)
    var words: List[String] = ["repair", "unicode", "sum"]
    assert_true(similarity(encode(words), atom("sum")) > 0.4)
    assert_true(similarity(encode(words), atom("unrelated")) < 0.2)
    assert_equal(len(a.values), DIM)
    print("PASS: determinism, full-token distinction, binding inverse, signed opposition, bundling")
