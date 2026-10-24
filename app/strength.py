"""Оценка надёжности пароля.

Считаем энтропию по размеру алфавита и длине, затем снижаем её за предсказуемые
шаблоны: словарные пароли, последовательности, повторы, даты, раскладку клавиатуры.
Итог — балл 0–4, оценка времени подбора и советы на русском.
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

COMMON = {
    line.strip()
    for line in (Path(__file__).parent / "common_passwords.txt").read_text(encoding="utf-8").splitlines()
    if line.strip()
}

LEET = str.maketrans({"@": "a", "4": "a", "3": "e", "1": "i", "!": "i", "0": "o", "$": "s", "5": "s", "7": "t"})
KEYBOARD_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю"]
SEQUENCES = ["abcdefghijklmnopqrstuvwxyz", "0123456789", "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"]

# Скорость перебора: офлайн-атака на быстрый хеш на видеокарте и онлайн-атака с ограничением попыток
GUESSES_OFFLINE = 1e10
GUESSES_ONLINE = 100 / 3600

LABELS = ["очень слабый", "слабый", "средний", "надёжный", "очень надёжный"]


@dataclass
class StrengthReport:
    score: int
    label: str
    entropy_bits: float
    crack_time_offline: str
    crack_time_online: str
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _pool_size(password: str) -> int:
    pool = 0
    if re.search(r"[a-z]", password):
        pool += 26
    if re.search(r"[A-Z]", password):
        pool += 26
    if re.search(r"\d", password):
        pool += 10
    if re.search(r"[а-яё]", password):
        pool += 33
    if re.search(r"[А-ЯЁ]", password):
        pool += 33
    if re.search(r"[^a-zA-Zа-яА-ЯёЁ\d]", password):
        pool += 33
    return pool


def _runs(text: str, alphabets: list[str], min_len: int = 3) -> int:
    """Сколько символов входит в прямые или обратные подряд идущие последовательности длиной от min_len."""
    lower = text.lower()
    covered = set()
    for alphabet in alphabets:
        for source in (alphabet, alphabet[::-1]):
            for i in range(len(lower) - min_len + 1):
                for j in range(len(lower), i + min_len - 1, -1):
                    if lower[i:j] in source:
                        covered.update(range(i, j))
                        break
    return len(covered)


YEAR = 365 * 24 * 3600
# После «около» числительное требует родительного падежа: около 1 часа, около 2 часов, около 21 дня
UNITS = [
    (YEAR, ("года", "лет")),
    (30 * 24 * 3600, ("месяца", "месяцев")),
    (24 * 3600, ("дня", "дней")),
    (3600, ("часа", "часов")),
    (60, ("минуты", "минут")),
    (1, ("секунды", "секунд")),
]


def _plural(n: int, forms: tuple[str, str]) -> str:
    return forms[0] if n % 10 == 1 and n % 100 != 11 else forms[1]


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return "мгновенно"
    if seconds >= 1000 * YEAR:
        return "больше тысячи лет"
    for size, forms in UNITS:
        if seconds >= size:
            n = round(seconds / size)
            return f"около {n} {_plural(n, forms)}"
    return "мгновенно"


# Балл по времени офлайн-подбора: меньше часа, суток, года, тысячи лет и больше
SCORE_LIMITS = [3600, 24 * 3600, YEAR, 1000 * YEAR]


def check(password: str) -> StrengthReport:
    warnings: list[str] = []
    suggestions: list[str] = []

    if not password:
        return StrengthReport(0, LABELS[0], 0.0, "мгновенно", "мгновенно", ["пароль пустой"], ["введите пароль"])

    length = len(password)
    entropy = length * math.log2(max(_pool_size(password), 1))

    normalized = password.lower().translate(LEET)
    if password.lower() in COMMON or normalized in COMMON:
        entropy = min(entropy, 10.0)
        warnings.append("пароль есть в списках самых популярных — его подберут первым")
    elif any(len(word) >= 4 and word in normalized for word in COMMON):
        entropy *= 0.6
        warnings.append("внутри пароля есть популярное слово или пароль")

    seq = _runs(password, SEQUENCES)
    kbd = _runs(password, KEYBOARD_ROWS)
    predictable = max(seq, kbd)
    if predictable:
        entropy -= predictable * math.log2(max(_pool_size(password), 2)) * 0.8
        warnings.append("есть последовательности вроде «abc», «123» или «qwerty»")

    repeats = sum(len(m.group(0)) - 1 for m in re.finditer(r"(.)\1{2,}", password))
    if repeats:
        entropy -= repeats * 2.5
        warnings.append("один и тот же символ повторяется подряд")

    if re.search(r"(19|20)\d{2}", password) or re.search(r"\d{2}[./-]?\d{2}[./-]?\d{2,4}", password):
        entropy -= 8
        warnings.append("похоже на год или дату — их легко угадать")

    if re.fullmatch(r"[A-Za-zА-Яа-яЁё]+\d{1,4}[!?.]?", password):
        entropy -= 6
        warnings.append("шаблон «слово + цифры в конце» перебирают в первую очередь")

    entropy = max(entropy, 0.0)

    if length < 12:
        suggestions.append("сделайте пароль длиннее: от 12 символов")
    if not re.search(r"[^a-zA-Zа-яА-ЯёЁ\d]", password):
        suggestions.append("добавьте спецсимволы: ! # % & …")
    if not (re.search(r"[a-zа-яё]", password) and re.search(r"[A-ZА-ЯЁ]", password)):
        suggestions.append("используйте и строчные, и заглавные буквы")
    if warnings:
        suggestions.append("лучше всего — случайный пароль из генератора")

    guesses = 2**entropy / 2
    offline_seconds = guesses / GUESSES_OFFLINE
    score = sum(offline_seconds >= limit for limit in SCORE_LIMITS)
    if warnings and score == 4:
        score = 3  # пароль с предсказуемым шаблоном не называем «очень надёжным»

    return StrengthReport(
        score=score,
        label=LABELS[score],
        entropy_bits=round(entropy, 1),
        crack_time_offline=format_duration(offline_seconds),
        crack_time_online=format_duration(guesses / GUESSES_ONLINE),
        warnings=warnings,
        suggestions=suggestions if score < 4 else [],
    )
