"""Verifica contraste e uso de tokens nas regras do tema escuro."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLESHEET_PATH = PROJECT_ROOT / "web_app" / "static" / "css" / "styles.css"
THEME_CONTRACT_MARKER = "/* Contrato visual Dark: novas regras devem usar variáveis de tema. */"
RULE_PATTERN = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)
BACKGROUND_PATTERN = re.compile(r"(?:background|background-color)\s*:\s*(?P<value>[^;]+)", re.IGNORECASE)
COLOR_PATTERN = re.compile(r"(?P<property>color|border(?:-[\w-]+)?(?:-color)?)\s*:\s*(?P<value>[^;]+)", re.IGNORECASE)
HEX_PATTERN = re.compile(r"#[0-9a-f]{3,8}\b", re.IGNORECASE)
RGB_PATTERN = re.compile(r"rgba?\(\s*([0-9.]+)[,\s]+([0-9.]+)[,\s]+([0-9.]+)", re.IGNORECASE)
THEME_VARIABLE_PATTERN = re.compile(r"var\(--(?:theme|state)-[\w-]+\)", re.IGNORECASE)
OPERATIONAL_SELECTOR_PATTERN = re.compile(
    r"\.(?:planning(?:[-_]|\b)|empty-state(?:[-_]|\b)|section-caption(?:[-_]|\b))",
    re.IGNORECASE,
)
LITERAL_COLOR_PATTERN = re.compile(r"(?:#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|\b(?:white|black)\b)", re.IGNORECASE)
NATIVE_DARK_SELECTOR_PATTERN = re.compile(
    r"(?:\b(?:input|textarea|select|option)(?:\b|\[)|\.app-modal(?:[-\w]*)?)",
    re.IGNORECASE,
)


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


def _relative_luminance(value: str) -> float | None:
    """Calcula luminância relativa do primeiro literal de cor encontrado."""

    hex_value = HEX_PATTERN.search(value.lower())
    if hex_value:
        digits = hex_value.group(0)[1:]
        if len(digits) in {4, 8}:
            digits = digits[:3]
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        channels = [int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    else:
        rgb_value = RGB_PATTERN.search(value.lower())
        if not rgb_value:
            return 1.0 if re.search(r"\bwhite\b", value.lower()) else None
        channels = [float(channel) / 255 for channel in rgb_value.groups()]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: float, background: float) -> float:
    lighter, darker = max(foreground, background), min(foreground, background)
    return (lighter + 0.05) / (darker + 0.05)


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


def find_low_contrast_dark_text(css_text: str) -> list[tuple[int, str, str]]:
    """Detecta texto literal com contraste inferior a 3:1 no fundo Dark."""

    findings: list[tuple[int, str, str]] = []
    dark_page_luminance = _relative_luminance("#0b1118") or 0
    for rule in RULE_PATTERN.finditer(css_text):
        selectors = " ".join(rule.group("selectors").split())
        if 'body[data-theme="dark"]' not in selectors:
            continue
        for declaration in COLOR_PATTERN.finditer(rule.group("body")):
            if declaration.group("property").lower() != "color":
                continue
            value = declaration.group("value").strip()
            foreground = _relative_luminance(value)
            if foreground is None or _contrast_ratio(foreground, dark_page_luminance) >= 3:
                continue
            line = css_text.count("\n", 0, rule.start() + declaration.start()) + 1
            findings.append((line, selectors, value))
    return findings


def find_light_dark_borders(css_text: str) -> list[tuple[int, str, str]]:
    """Detecta bordas literais muito claras em componentes Dark."""

    findings: list[tuple[int, str, str]] = []
    for rule in RULE_PATTERN.finditer(css_text):
        selectors = " ".join(rule.group("selectors").split())
        if 'body[data-theme="dark"]' not in selectors:
            continue
        for declaration in COLOR_PATTERN.finditer(rule.group("body")):
            if not declaration.group("property").lower().startswith("border"):
                continue
            value = declaration.group("value").strip()
            if not _contains_light_literal(value):
                continue
            line = css_text.count("\n", 0, rule.start() + declaration.start()) + 1
            findings.append((line, selectors, value))
    return findings


def find_dark_components_without_theme_variables(css_text: str) -> list[tuple[int, str, str]]:
    """Exige tokens de tema nas novas regras Dark após o marcador de contrato."""

    if THEME_CONTRACT_MARKER not in css_text:
        return [(1, "<stylesheet>", "marcador do contrato visual Dark ausente")]
    marker_position = css_text.find(THEME_CONTRACT_MARKER)
    contract_css = css_text[marker_position + len(THEME_CONTRACT_MARKER) :]
    findings: list[tuple[int, str, str]] = []
    for rule in RULE_PATTERN.finditer(contract_css):
        selectors = " ".join(rule.group("selectors").split())
        if 'body[data-theme="dark"]' not in selectors:
            continue
        declarations = list(BACKGROUND_PATTERN.finditer(rule.group("body"))) + list(COLOR_PATTERN.finditer(rule.group("body")))
        if not declarations or any(THEME_VARIABLE_PATTERN.search(declaration.group(0)) for declaration in declarations):
            continue
        if all(re.search(r"\b(?:transparent|inherit|currentcolor)\b", declaration.group(0), re.IGNORECASE) for declaration in declarations):
            continue
        line = css_text.count("\n", 0, marker_position + len(THEME_CONTRACT_MARKER) + rule.start()) + 1
        findings.append((line, selectors, "componente sem variável --theme-* ou --state-*"))
    return findings


def find_native_dark_components_without_theme_variables(css_text: str) -> list[tuple[int, str, str]]:
    """Verifica tokens nos campos nativos e modais do contrato Dark."""

    if THEME_CONTRACT_MARKER not in css_text:
        return [(1, "<stylesheet>", "marcador do contrato visual Dark ausente")]
    marker_position = css_text.find(THEME_CONTRACT_MARKER)
    contract_css = css_text[marker_position + len(THEME_CONTRACT_MARKER) :]
    findings: list[tuple[int, str, str]] = []
    for rule in RULE_PATTERN.finditer(contract_css):
        selectors = " ".join(rule.group("selectors").split())
        if 'body[data-theme="dark"]' not in selectors or not NATIVE_DARK_SELECTOR_PATTERN.search(selectors):
            continue
        declarations = list(BACKGROUND_PATTERN.finditer(rule.group("body"))) + list(COLOR_PATTERN.finditer(rule.group("body")))
        if not declarations:
            continue
        if all(THEME_VARIABLE_PATTERN.search(declaration.group("value")) for declaration in declarations):
            continue
        line = css_text.count("\n", 0, marker_position + len(THEME_CONTRACT_MARKER) + rule.start()) + 1
        findings.append((line, selectors, "campo nativo ou modal sem variável --theme-*"))
    return findings


def find_fixed_operational_colors(css_text: str) -> list[tuple[int, str, str]]:
    """Detecta cores literais em superfícies operacionais que deveriam usar tokens."""

    findings: list[tuple[int, str, str]] = []
    for rule in RULE_PATTERN.finditer(css_text):
        selectors = " ".join(rule.group("selectors").split())
        if not OPERATIONAL_SELECTOR_PATTERN.search(selectors):
            continue
        if 'body[data-theme="dark"]' in selectors:
            continue
        for declaration in list(BACKGROUND_PATTERN.finditer(rule.group("body"))) + list(COLOR_PATTERN.finditer(rule.group("body"))):
            value = declaration.group("value").strip()
            if THEME_VARIABLE_PATTERN.search(value) or not LITERAL_COLOR_PATTERN.search(value):
                continue
            property_name = declaration.group(0).split(":", 1)[0].strip().lower()
            # Fundos claros são sempre uma divergência no Dark. Textos e bordas
            # literais também entram no alerta para evitar novas exceções visuais.
            if property_name.startswith("background") and not _contains_light_literal(value):
                continue
            line = css_text.count("\n", 0, rule.start() + declaration.start()) + 1
            findings.append((line, selectors, f"{property_name}: {value}"))
    return findings


def main() -> int:
    css_text = STYLESHEET_PATH.read_text(encoding="utf-8")
    checks = [
        ("fundos claros", find_light_dark_backgrounds(css_text)),
        ("texto com baixo contraste", find_low_contrast_dark_text(css_text)),
        ("bordas claras", find_light_dark_borders(css_text)),
        ("componentes sem tokens", find_dark_components_without_theme_variables(css_text)),
        ("campos nativos e modais sem tokens", find_native_dark_components_without_theme_variables(css_text)),
        ("cores fixas em componentes operacionais", find_fixed_operational_colors(css_text)),
    ]
    findings = [(category, finding) for category, category_findings in checks for finding in category_findings]
    if not findings:
        print(f"OK: contraste, bordas e tokens Dark validados em {STYLESHEET_PATH}")
        return 0
    print("FALHA: divergencias encontradas nas regras do tema Dark:")
    for category, (line, selector, value) in findings:
        print(f"  [{category}] linha {line}: {selector} -> {value}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
