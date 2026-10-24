"""Криптостойкий генератор паролей на модуле secrets."""

import secrets
import string
from dataclasses import dataclass

from app.strength import check

AMBIGUOUS = set("Il1O0o|`'\"")
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/~"

MIN_LENGTH = 6
MAX_LENGTH = 128
MAX_ATTEMPTS = 20


@dataclass(frozen=True)
class GeneratorOptions:
    length: int = 16
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    exclude_ambiguous: bool = False


def _charsets(opts: GeneratorOptions) -> list[str]:
    sets = []
    if opts.lower:
        sets.append(string.ascii_lowercase)
    if opts.upper:
        sets.append(string.ascii_uppercase)
    if opts.digits:
        sets.append(string.digits)
    if opts.symbols:
        sets.append(SYMBOLS)
    if opts.exclude_ambiguous:
        sets = ["".join(c for c in s if c not in AMBIGUOUS) for s in sets]
    return sets


def generate(opts: GeneratorOptions) -> str:
    """Возвращает пароль, в котором есть хотя бы один символ из каждого выбранного набора."""
    if not MIN_LENGTH <= opts.length <= MAX_LENGTH:
        raise ValueError(f"длина должна быть от {MIN_LENGTH} до {MAX_LENGTH}")
    sets = _charsets(opts)
    if not sets:
        raise ValueError("выберите хотя бы один набор символов")
    if opts.length < len(sets):
        raise ValueError("длина меньше числа выбранных наборов символов")

    # Случайно сложившиеся «abc», «111» или «1990» подбираются по шаблонам первыми — такие варианты
    # пересоздаём. Отбрасывается доля процента всех паролей, на энтропию это почти не влияет.
    best: tuple[int, str] | None = None
    for _ in range(MAX_ATTEMPTS):
        candidate = _draw(sets, opts.length)
        warnings = len(check(candidate).warnings)
        if not warnings:
            return candidate
        if best is None or warnings < best[0]:
            best = (warnings, candidate)
    # например, длинный пароль только из цифр почти всегда содержит «год» — отдаём лучший из найденных
    return best[1]


def _draw(sets: list[str], length: int) -> str:
    alphabet = "".join(sets)
    chars = [secrets.choice(s) for s in sets]
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    # перемешиваем, чтобы обязательные символы не стояли всегда в начале
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def alphabet_size(opts: GeneratorOptions) -> int:
    return len("".join(_charsets(opts)))
