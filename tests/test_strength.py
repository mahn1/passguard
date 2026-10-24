import pytest

from app.generator import GeneratorOptions, generate
from app.strength import check, format_duration


@pytest.mark.parametrize("password", ["123456", "qwerty", "password", "пароль", "йцукен", "P@ssw0rd"])
def test_common_passwords_are_very_weak(password):
    report = check(password)
    assert report.score == 0
    assert report.warnings


def test_word_with_year_is_weak():
    report = check("Masha1995")
    assert report.score <= 1
    assert any("год" in w for w in report.warnings)


def test_keyboard_sequence_is_penalized():
    assert check("asdfghjkl1").score <= 1


def test_random_password_is_very_strong():
    report = check(generate(GeneratorOptions(length=16)))
    assert report.score == 4
    assert report.suggestions == []


def test_warnings_cap_score():
    assert check("Kotik2024!").score <= 3


def test_empty_password():
    report = check("")
    assert report.score == 0
    assert report.entropy_bits == 0


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.5, "мгновенно"),
        (41, "около 41 секунды"),
        (2 * 3600, "около 2 часов"),
        (21 * 24 * 3600, "около 21 дня"),
        (11 * 24 * 3600, "около 11 дней"),
        (5 * 365 * 24 * 3600, "около 5 лет"),
        (1e12, "больше тысячи лет"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected
