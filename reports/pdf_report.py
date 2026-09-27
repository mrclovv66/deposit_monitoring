from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT_DIR = Path("output")

VTB_RANGES_FILE = OUTPUT_DIR / "vtb_ranges.json"
RSHB_RANGES_FILE = OUTPUT_DIR / "rshb_ranges.json"
SBER_RANGES_FILE = OUTPUT_DIR / "sber_ranges.json"


def register_font() -> str:
    font_paths = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
    ]

    for font_path in font_paths:
        if font_path.exists():
            if "RussianFont" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(
                    TTFont(
                        "RussianFont",
                        str(font_path),
                    )
                )

            return "RussianFont"

    raise RuntimeError(
        "Не найден Arial, Calibri или Tahoma "
        "в C:\\Windows\\Fonts"
    )


def load_json(
    file_path: Path,
) -> list[dict[str, Any]]:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Файл не найден: {file_path.resolve()}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"В {file_path.name} ожидался JSON-массив"
        )

    return [
        row
        for row in data
        if isinstance(row, dict)
    ]


def format_money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₽"


def format_rate(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def format_term(
    term_from: int,
    term_to: int,
) -> str:
    if term_from == term_to:
        return str(term_from)

    return f"{term_from}–{term_to}"


def yes_no(value: bool) -> str:
    return "Да" if value else "Нет"


def create_styles(
    font_name: str,
) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            name="TitleStyle",
            fontName=font_name,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "subtitle": ParagraphStyle(
            name="SubtitleStyle",
            fontName=font_name,
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        ),
        "section": ParagraphStyle(
            name="SectionStyle",
            fontName=font_name,
            fontSize=13,
            leading=16,
            alignment=TA_LEFT,
            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
        ),
        "cell": ParagraphStyle(
            name="CellStyle",
            fontName=font_name,
            fontSize=7,
            leading=8.5,
            alignment=TA_CENTER,
        ),
        "header": ParagraphStyle(
            name="HeaderStyle",
            fontName=font_name,
            fontSize=7,
            leading=8.5,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "note": ParagraphStyle(
            name="NoteStyle",
            fontName=font_name,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#555555"),
        ),
    }


def paragraph(
    value: Any,
    style: ParagraphStyle,
) -> Paragraph:
    return Paragraph(
        str(value),
        style,
    )


def build_table(
    rows: list[dict[str, Any]],
    font_name: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    headers = [
        "Продукт",
        "Сумма от",
        "Сумма до",
        "Срок, дней",
        "Ставка",
        "Выплата процентов",
        "Пополнение",
        "Частичное снятие",
    ]

    table_data: list[list[Any]] = [
        [
            paragraph(
                header,
                styles["header"],
            )
            for header in headers
        ]
    ]

    for row in rows:
        table_data.append(
            [
                paragraph(
                    row.get("product_name", ""),
                    styles["cell"],
                ),
                paragraph(
                    format_money(
                        int(row.get("amount_from", 0))
                    ),
                    styles["cell"],
                ),
                paragraph(
                    format_money(
                        int(row.get("amount_to", 0))
                    ),
                    styles["cell"],
                ),
                paragraph(
                    format_term(
                        int(row.get("term_from", 0)),
                        int(row.get("term_to", 0)),
                    ),
                    styles["cell"],
                ),
                paragraph(
                    format_rate(
                        float(row.get("rate", 0))
                    ),
                    styles["cell"],
                ),
                paragraph(
                    row.get("payment_name", ""),
                    styles["cell"],
                ),
                paragraph(
                    yes_no(
                        bool(
                            row.get(
                                "replenishment",
                                False,
                            )
                        )
                    ),
                    styles["cell"],
                ),
                paragraph(
                    yes_no(
                        bool(
                            row.get(
                                "partial_withdrawal",
                                False,
                            )
                        )
                    ),
                    styles["cell"],
                ),
            ]
        )

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            42 * mm,
            31 * mm,
            31 * mm,
            22 * mm,
            20 * mm,
            31 * mm,
            24 * mm,
            30 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#0B3A82"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    font_name,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    colors.HexColor("#777777"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F2F5F9"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def generate_bank_pdf(
    bank_name: str,
    file_prefix: str,
    input_file: Path,
    note: str,
) -> Path:
    rows = load_json(input_file)

    if not rows:
        raise RuntimeError(
            f"В файле {input_file.name} нет данных"
        )

    font_name = register_font()
    styles = create_styles(font_name)
    generated_at = datetime.now()

    output_path = OUTPUT_DIR / (
        f"{file_prefix}_ставки_{generated_at:%d-%m-%Y}.pdf"
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Депозитные ставки {bank_name}",
        author="Deposit Monitor",
    )

    sections: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:
        section = str(
            row.get(
                "section",
                "Депозиты",
            )
        )

        sections.setdefault(
            section,
            [],
        ).append(row)

    story: list[Any] = [
        Paragraph(
            bank_name,
            styles["title"],
        ),
        Paragraph(
            "Депозитные ставки для юридических лиц",
            styles["subtitle"],
        ),
        Paragraph(
            (
                "Дата и время формирования: "
                f"{generated_at:%d.%m.%Y %H:%M}"
            ),
            styles["subtitle"],
        ),
        Spacer(
            1,
            3 * mm,
        ),
    ]

    section_names = sorted(
        sections.keys(),
        key=lambda name: (
            0 if "Овернайт" in name else 1,
            name,
        ),
    )

    for index, section_name in enumerate(section_names):
        section_rows = sorted(
            sections[section_name],
            key=lambda row: (
                str(row.get("product_name", "")),
                int(row.get("term_from", 0)),
                int(row.get("amount_from", 0)),
                -float(row.get("rate", 0)),
            ),
        )

        story.append(
            Paragraph(
                section_name,
                styles["section"],
            )
        )

        story.append(
            build_table(
                section_rows,
                font_name,
                styles,
            )
        )

        if index < len(section_names) - 1:
            story.append(
                PageBreak()
            )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            note,
            styles["note"],
        )
    )

    document.build(story)

    return output_path


def generate_vtb_pdf() -> Path:
    return generate_bank_pdf(
        bank_name="ВТБ",
        file_prefix="ВТБ",
        input_file=VTB_RANGES_FILE,
        note=(
            "Ставки получены с публичного калькулятора ВТБ. "
            "Фактические условия могут зависеть от параметров "
            "конкретного юридического лица."
        ),
    )


def generate_rshb_pdf() -> Path:
    return generate_bank_pdf(
        bank_name="Россельхозбанк",
        file_prefix="РСХБ",
        input_file=RSHB_RANGES_FILE,
        note=(
            "В отчёте показаны контрольные сроки. "
            "Ставки получены с публичного калькулятора "
            "Россельхозбанка."
        ),
    )


def generate_sber_pdf() -> Path:
    return generate_bank_pdf(
        bank_name="Сбербанк",
        file_prefix="Сбербанк",
        input_file=SBER_RANGES_FILE,
        note=(
            "Ставки получены с публичного калькулятора "
            "Сбербанка для юридических лиц."
        ),
    )