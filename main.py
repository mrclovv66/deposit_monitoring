from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from banks.rshb import get_rshb_rates
from banks.sber import (
    SBER_PRODUCTS,
    SberProduct,
    get_sber_rate,
)
from banks.vtb import get_vtb_rates
from processors.rate_ranges import (
    build_rshb_ranges,
    build_sber_amount_ranges,
    build_vtb_amount_ranges,
)
from reports.pdf_report import (
    generate_rshb_pdf,
    generate_sber_pdf,
    generate_vtb_pdf,
)


OUTPUT_DIR = Path("output")

VTB_RAW_FILE = OUTPUT_DIR / "vtb_rates.json"
VTB_RANGES_FILE = OUTPUT_DIR / "vtb_ranges.json"

RSHB_RAW_FILE = OUTPUT_DIR / "rshb_rates.json"
RSHB_RANGES_FILE = OUTPUT_DIR / "rshb_ranges.json"

SBER_RAW_FILE = OUTPUT_DIR / "sber_rates.json"
SBER_RANGES_FILE = OUTPUT_DIR / "sber_ranges.json"


TESTED_AMOUNTS = [
    50_000,
    100_000,
    500_000,
    1_000_000,
    5_000_000,
    10_000_000,
    50_000_000,
    100_000_000,
]

VTB_TERMS = [
    1,
    2,
    3,
    7,
    14,
    30,
    60,
    90,
    180,
    365,
]

VTB_PAYMENT_CODES = [
    "end",
    "monthly",
    "start",
]

SBER_PRODUCT_TERMS = {
    "Classic": [
        1,
        7,
        14,
        30,
        31,
        60,
        61,
        90,
        92,
        180,
        365,
    ],
    "Otz": [
        31,
        61,
        92,
    ],
    "Pop": [
        31,
        61,
        92,
    ],
    "NSO": [
        1,
        7,
        14,
        30,
        31,
        60,
        61,
        90,
        92,
        180,
        365,
    ],
}


def format_money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def save_json(
    file_path: Path,
    data: list[dict[str, Any]],
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = file_path.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary_file.replace(
        file_path
    )


# ============================================================
# ВТБ
# ============================================================

def collect_vtb_rates() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    total_requests = (
        len(TESTED_AMOUNTS)
        * len(VTB_TERMS)
        * len(VTB_PAYMENT_CODES)
    )

    request_number = 0

    print()
    print("=" * 90)
    print("ВТБ — СБОР СТАВОК")
    print("=" * 90)

    for amount in TESTED_AMOUNTS:
        for term in VTB_TERMS:
            for payment_code in VTB_PAYMENT_CODES:
                request_number += 1

                print(
                    f"[ВТБ {request_number}/{total_requests}] "
                    f"{format_money(amount)} ₽ | "
                    f"{term} дней | {payment_code}"
                )

                try:
                    rates = get_vtb_rates(
                        amount=amount,
                        term=term,
                        payment_code=payment_code,
                    )

                    for rate in rates:
                        if not rate.is_active:
                            continue

                        result.append(
                            {
                                "amount": amount,
                                "term": term,
                                "payment_code": payment_code,
                                **asdict(rate),
                            }
                        )

                except Exception as error:
                    print(
                        f"Ошибка ВТБ: {error}"
                    )

                time.sleep(0.2)

    return result


def process_vtb() -> Path:
    raw_rows = collect_vtb_rates()

    if not raw_rows:
        raise RuntimeError(
            "ВТБ не вернул ставок"
        )

    range_rows = build_vtb_amount_ranges(
        raw_rows,
        TESTED_AMOUNTS,
    )

    save_json(
        VTB_RAW_FILE,
        raw_rows,
    )

    save_json(
        VTB_RANGES_FILE,
        range_rows,
    )

    return generate_vtb_pdf()


# ============================================================
# РОССЕЛЬХОЗБАНК
# ============================================================

def process_rshb() -> Path:
    print()
    print("=" * 90)
    print("РОССЕЛЬХОЗБАНК — СБОР СТАВОК")
    print("=" * 90)

    raw_rows = [
        asdict(rate)
        for rate in get_rshb_rates()
    ]

    if not raw_rows:
        raise RuntimeError(
            "Россельхозбанк не вернул ставок"
        )

    range_rows = build_rshb_ranges(
        raw_rows
    )

    save_json(
        RSHB_RAW_FILE,
        raw_rows,
    )

    save_json(
        RSHB_RANGES_FILE,
        range_rows,
    )

    return generate_rshb_pdf()


# ============================================================
# СБЕРБАНК
# ============================================================

def find_sber_product(
    product_code: str,
) -> SberProduct:
    for product in SBER_PRODUCTS:
        if product.product_code == product_code:
            return product

    raise KeyError(
        f"Продукт Сбера не найден: {product_code}"
    )


def collect_sber_rates() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    total_requests = sum(
        len(TESTED_AMOUNTS) * len(terms)
        for terms in SBER_PRODUCT_TERMS.values()
    )

    request_number = 0

    print()
    print("=" * 90)
    print("СБЕРБАНК — СБОР СТАВОК")
    print("=" * 90)

    for product_code, terms in SBER_PRODUCT_TERMS.items():
        product = find_sber_product(
            product_code
        )

        for amount in TESTED_AMOUNTS:
            for term in terms:
                request_number += 1

                print(
                    f"[СБЕР {request_number}/{total_requests}] "
                    f"{product.product_name} | "
                    f"{format_money(amount)} ₽ | "
                    f"{term} дней"
                )

                try:
                    rate = get_sber_rate(
                        product=product,
                        amount=amount,
                        term=term,
                        client_type=1,
                    )

                    if rate.is_active:
                        result.append(
                            asdict(rate)
                        )

                except Exception as error:
                    print(
                        "Ошибка Сбера: "
                        f"{product.product_code}, "
                        f"{amount}, {term}: {error}"
                    )

                time.sleep(0.2)

    return result


def process_sber() -> Path:
    raw_rows = collect_sber_rates()

    if not raw_rows:
        raise RuntimeError(
            "Сбербанк не вернул ставок"
        )

    range_rows = build_sber_amount_ranges(
        raw_rows,
        TESTED_AMOUNTS,
    )

    save_json(
        SBER_RAW_FILE,
        raw_rows,
    )

    save_json(
        SBER_RANGES_FILE,
        range_rows,
    )

    return generate_sber_pdf()


# ============================================================
# ОБЩИЙ ЗАПУСК
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 90)
    print("МОНИТОРИНГ ДЕПОЗИТНЫХ СТАВОК")
    print("=" * 90)

    created_pdfs: list[Path] = []
    errors: list[str] = []

    banks = [
        ("ВТБ", process_vtb),
        ("Россельхозбанк", process_rshb),
        ("Сбербанк", process_sber),
    ]

    for bank_name, process_function in banks:
        try:
            pdf_path = process_function()
            created_pdfs.append(pdf_path)

            print()
            print(
                f"{bank_name}: успешно"
            )
            print(
                f"PDF: {pdf_path.resolve()}"
            )

        except Exception as error:
            errors.append(
                f"{bank_name}: {error}"
            )

            print()
            print(
                f"{bank_name}: ошибка — {error}"
            )

    print()
    print("=" * 90)
    print("ИТОГ")
    print("=" * 90)

    if created_pdfs:
        print("Созданные PDF:")

        for pdf_path in created_pdfs:
            print(
                f"- {pdf_path.resolve()}"
            )

    if errors:
        print()
        print("Ошибки:")

        for error in errors:
            print(
                f"- {error}"
            )

    if not created_pdfs:
        raise SystemExit(
            "Не удалось создать ни одного PDF"
        )


if __name__ == "__main__":
    main()