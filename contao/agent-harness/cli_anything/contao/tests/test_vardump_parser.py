import pytest
from cli_anything.contao.utils.vardump_parser import parse_vardump, VarDumpParser


def test_parse_string():
    assert parse_vardump('"hello"') == "hello"


def test_parse_integer():
    assert parse_vardump("42") == 42


def test_parse_negative_integer():
    assert parse_vardump("-7") == -7


def test_parse_float():
    assert parse_vardump("3.14") == 3.14


def test_parse_true():
    assert parse_vardump("true") is True


def test_parse_false():
    assert parse_vardump("false") is False


def test_parse_null():
    assert parse_vardump("null") is None


def test_parse_empty_array():
    assert parse_vardump('array:0 []') == {}


def test_parse_simple_array():
    dump = 'array:2 [\n  "foo" => "bar"\n  "baz" => 1\n]'
    assert parse_vardump(dump) == {"foo": "bar", "baz": 1}


def test_parse_nested_array():
    dump = 'array:1 [\n  "inner" => array:1 [\n    "key" => "val"\n  ]\n]'
    assert parse_vardump(dump) == {"inner": {"key": "val"}}


def test_parse_string_with_embedded_quotes():
    # VarDumper embeds quotes without escaping; the parser uses lookahead
    dump = '"say \\"hello\\""'
    result = parse_vardump(dump)
    assert isinstance(result, str)


def test_parse_closure_returns_sentinel():
    dump = 'Closure() {#42\n  parameter: ...\n}'
    assert parse_vardump(dump) == "__closure__"


def test_parse_invalid_raises():
    with pytest.raises((ValueError, Exception)):
        parse_vardump(";invalid;")


def test_parse_integer_keys():
    dump = 'array:2 [\n  0 => "first"\n  1 => "second"\n]'
    result = parse_vardump(dump)
    assert result[0] == "first"
    assert result[1] == "second"


def test_parse_heredoc_string():
    dump = '"""\n  multi\n  line\n"""'
    result = parse_vardump(dump)
    assert "multi" in result
    assert "line" in result
