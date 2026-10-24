"""Криптостойкий генератор паролей на модуле secrets."""

import secrets
import string
from dataclasses import dataclass

AMBIGUOUS = set("Il1O0o|`'\"")
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/~"

MIN_LENGTH = 6
MAX_LENGTH = 128


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

    alphabet = "".join(sets)
    chars = [secrets.choice(s) for s in sets]
    chars += [secrets.choice(alphabet) for _ in range(opts.length - len(chars))]
    # перемешиваем, чтобы обязательные символы не стояли всегда в начале
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def alphabet_size(opts: GeneratorOptions) -> int:
    return len("".join(_charsets(opts)))
