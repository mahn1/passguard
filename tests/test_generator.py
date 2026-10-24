import string

import pytest

from app.generator import AMBIGUOUS, SYMBOLS, GeneratorOptions, generate
from app.strength import check


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


@pytest.mark.parametrize("length", [16, 24])
def test_generated_passwords_are_always_very_strong(length):
    for _ in range(3000):
        report = check(generate(GeneratorOptions(length=length)))
        assert report.score == 4 and not report.warnings


def test_digits_only_still_returns_password():
    # в 60 цифрах почти наверняка найдётся «год» — генератор не должен зацикливаться
    assert len(generate(GeneratorOptions(length=60, lower=False, upper=False, symbols=False))) == 60


def test_passwords_are_unique():
    assert len({generate(GeneratorOptions()) for _ in range(200)}) == 200


@pytest.mark.parametrize("length", [5, 129])
def test_bad_length(length):
    with pytest.raises(ValueError):
        generate(GeneratorOptions(length=length))


def test_no_sets():
    with pytest.raises(ValueError):
        generate(GeneratorOptions(lower=False, upper=False, digits=False, symbols=False))
