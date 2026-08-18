"""Verifica fundos claros inseridos diretamente nas regras do tema escuro."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLESHEET_PATH = PROJECT_ROOT / "web_app" / "static" / "css" / "styles.css"
RULE_PATTERN = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)
BACKGROUND_PATTERN = re.compile(r"(?:background|background-color)\s*:\s*(?P<value>[^;]+)", re.IGNORECASE)
HEX_PATTERN = re.compile(r"#[0-9a-f]{3,8}\b", re.IGNORECASE)
RGB_PATTERN = re.compile(r"rgba?\(\s*([0-9.]+)[,\s]+([0-9.]+)[,\s]+([0-9.]+)", re.IGNORECASE)


def _hex_luminance(value: str) -> float:
    digits = value[1:]
    if len(digits) in {4, 8}:
        digits = digits[:3]
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    red, green, blue = (int(digits[index : index + 2], 16) for index in (0, 2, 4))
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255


def _contains_light_literal(value: str) -> bool:
    normalized = value.lower()
    if re.search(r"\bwhite\b", normalized):
        return True
    if any(_hex_luminance(token) >= 0.78 for token in HEX_PATTERN.findall(normalized)):
        return True
    return any(
        (0.2126 * float(red) + 0.7152 * float(green) + 0.0722 * float(blue)) / 255 >= 0.78
        for red, green, blue in RGB_PATTERN.findall(normalized)
    )


def find_light_dark_backgrounds(css_text: str) -> list[tuple[int, str, str]]:
    """Retorna (linha, seletor, valor) para fundos claros em regras Dark."""

    findings: list[tuple[int, str, str]] = []
    for rule in RULE_PATTERN.finditer(css_text):
        selectors = " ".join(rule.group("selectors").split())
        if 'body[data-theme="dark"]' not in selectors:
            continue
        for declaration in BACKGROUND_PATTERN.finditer(rule.group("body")):
            value = declaration.group("value").strip()
            if _contains_light_literal(value):
                line = css_text.count("\n", 0, rule.start() + declaration.start()) + 1
                findings.append((line, selectors, value))
    return findings


def main() -> int:
    findings = find_light_dark_backgrounds(STYLESHEET_PATH.read_text(encoding="utf-8"))
    if not findings:
        print(f"OK: nenhuma superfície clara literal nas regras Dark de {STYLESHEET_PATH}")
        return 0
    print("FALHA: fundos claros encontrados nas regras do tema Dark:")
    for line, selector, value in findings:
        print(f"  linha {line}: {selector} -> {value}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
