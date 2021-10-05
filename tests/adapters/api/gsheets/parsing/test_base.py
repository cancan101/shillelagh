"""
Test the base parser/tokenizer.
"""
# pylint: disable=protected-access
from datetime import datetime

from shillelagh.adapters.api.gsheets.parsing.base import is_unescaped_literal
from shillelagh.adapters.api.gsheets.parsing.base import LITERAL
from shillelagh.adapters.api.gsheets.parsing.base import tokenize
from shillelagh.adapters.api.gsheets.parsing.datetime import DD
from shillelagh.adapters.api.gsheets.parsing.datetime import MM
from shillelagh.adapters.api.gsheets.parsing.datetime import YYYY


def test_literal_token():
    """
    Test the literal token.
    """
    classes = [
        DD,
        MM,
        YYYY,
        LITERAL,
    ]

    assert LITERAL.match(r"\d")
    assert LITERAL.match('"dd/mm/yy"')
    # matches eveything
    assert LITERAL.match("d")

    token = LITERAL("@")
    tokens = list(tokenize("@", classes))
    assert token.format(datetime(2021, 11, 12, 13, 14, 15, 16), tokens) == "@"

    token = LITERAL('"dd/mm/yy"')
    tokens = list(tokenize('"dd/mm/yy"', classes))
    assert token.format(datetime(2021, 11, 12, 13, 14, 15, 16), tokens) == "dd/mm/yy"

    token = LITERAL('"invalid"')
    assert token.parse("invalid", tokens) == ({}, "")

    token = LITERAL(r"\d")
    assert token.parse("d", tokens) == ({}, "")


def test_tokenize():
    """
    Test the tokenize function.
    """
    classes = [
        DD,
        MM,
        YYYY,
        LITERAL,
    ]
    tokens = list(tokenize('dd/mm/yyyy -> ("dd/mm/yyyy")', classes))
    assert tokens == [
        DD("dd"),
        LITERAL("/"),
        MM("mm"),
        LITERAL("/"),
        YYYY("yyyy"),
        LITERAL(" -> ("),
        LITERAL('"dd/mm/yyyy"'),
        LITERAL(")"),
    ]


def test_is_unescaped_literal():
    """
    Test the is_unescaped_literal function.
    """
    assert is_unescaped_literal(LITERAL("a"))
    assert not is_unescaped_literal(LITERAL(r"\d"))
    assert not is_unescaped_literal(LITERAL('"hello"'))
    assert not is_unescaped_literal(YYYY("yyyy"))