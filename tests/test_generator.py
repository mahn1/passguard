import string

import pytest

from app.generator import AMBIGUOUS, SYMBOLS, GeneratorOptions, generate


def test_default_has_every_char_class():
    for _ in range(50):
        p = generate(GeneratorOptions())
        assert len(p) == 16
        assert any(c in string.ascii_lowercase for c in p)
        assert any(c in string.ascii_uppercase for c in p)
        assert any(c in string.digits for c in p)
        assert any(c in SYMBOLS for c in p)


def test_only_digits():
    p = generate(GeneratorOptions(length=30, lower=False, upper=False, symbols=False))
    assert p.isdigit() and len(p) == 30


def test_exclude_ambiguous():
    for _ in range(50):
        assert not set(generate(GeneratorOptions(length=64, exclude_ambiguous=True))) & AMBIGUOUS


def test_passwords_are_unique():
    assert len({generate(GeneratorOptions()) for _ in range(200)}) == 200


@pytest.mark.parametrize("length", [5, 129])
def test_bad_length(length):
    with pytest.raises(ValueError):
        generate(GeneratorOptions(length=length))


def test_no_sets():
    with pytest.raises(ValueError):
        generate(GeneratorOptions(lower=False, upper=False, digits=False, symbols=False))
