"""终端输出清洗与输入校验。"""

from __future__ import annotations

import unicodedata


def is_dangerous_unicode(char: str) -> bool:
    return char in {
        "\u200b",
        "\u200c",
        "\u200d",
        "\ufeff",
        "\u2028",
        "\u2029",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    } or "\u202a" <= char <= "\u202e"


def _is_control_char(char: str) -> bool:
    return unicodedata.category(char).startswith("C")


def sanitize_for_terminal(text: str) -> str:
    """去除危险控制字符，但保留换行和制表符。"""
    chars: list[str] = []
    for char in text:
        if char in {"\n", "\t"}:
            chars.append(char)
            continue
        if _is_control_char(char) or is_dangerous_unicode(char):
            continue
        chars.append(char)
    return "".join(chars)


def reject_dangerous_chars(value: str, flag_name: str) -> None:
    for char in value:
        if _is_control_char(char) or is_dangerous_unicode(char):
            raise ValueError(f"{flag_name} 包含非法控制字符或危险 Unicode 字符")
