"""Regression: an impossible wildcard pattern must not burn regex budget."""
from openfeed.extract import extract_articles


def test_large_repetitive_page_with_missing_suffix_returns_no_items():
    html = '<main>' + 'x' * 50_000 + '</main>'
    result, _ = extract_articles(html, 'https://research.example/', {
        'mode': 'pattern', 'global_pattern': '<main>{%}</main>',
        'item_selector': 'x{%}y',
    })
    assert result == []


def test_invalid_pattern_still_raises_even_when_literals_are_missing():
    import pytest
    with pytest.raises(ValueError, match='Pattern requires'):
        extract_articles('<main>data</main>', 'https://research.example/', {
            'mode': 'pattern', 'item_selector': 'literal-without-a-capture',
        })
