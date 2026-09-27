from __future__ import annotations

from collections import defaultdict
from typing import Any


VTB_PRODUCT_NAMES = {
    "VTB_UNIVERSAL_RUB": "Универсальный",
    "VTB_NSO_RUB": "Неснижаемый остаток",
    "VTB_AVANS_RUB": "Авансовый",
    "VTB_FIX_RUB": "Фиксированный",
    "VTB_OVERNIGHT_RUB": "Овернайт",
    "VTB_FLEX_RUB": "Гибкий",
    "VTB_AUTOOVERNIGHT_RUB": "Автоматический овернайт",
}

PAYMENT_NAMES = {
    "end": "В конце срока",
    "monthly": "Ежемесячно",
    "start": "В начале срока",
}

RSHB_CONTROL_TERMS = [
    1,
    7,
    14,
    30,
    60,
    90,
    180,
    365,
]


def _remove_exact_duplicates(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}

    for row in rows:
        key = tuple(row.get(field) for field in fields)
        unique[key] = row

    return list(unique.values())


# ============================================================
# ВТБ
# ============================================================

def _make_vtb_range_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first = rows[0]

    amounts = sorted(
        int(row["amount"])
        for row in rows
    )

    product_code = str(
        first.get("product_code", "")
    )

    term = int(first.get("term", 0))
    payment_code = str(
        first.get("payment_code", "")
    )

    is_overnight = product_code in {
        "VTB_OVERNIGHT_RUB",
        "VTB_AUTOOVERNIGHT_RUB",
    }

    return {
        "bank": "ВТБ",
        "section": (
            "Овернайт"
            if is_overnight
            else "Срочные депозиты"
        ),
        "product_code": product_code,
        "product_name": VTB_PRODUCT_NAMES.get(
            product_code,
            product_code,
        ),
        "amount_from": amounts[0],
        "amount_to": amounts[-1],
        "term_from": term,
        "term_to": term,
        "payment_name": PAYMENT_NAMES.get(
            payment_code,
            payment_code,
        ),
        "rate": round(
            float(first.get("rate", 0)),
            4,
        ),
        "replenishment": bool(
            first.get("replenishment", False)
        ),
        "partial_withdrawal": bool(
            first.get(
                "partial_withdrawal",
                False,
            )
        ),
    }


def build_vtb_amount_ranges(
    rows: list[dict[str, Any]],
    tested_amounts: list[int],
) -> list[dict[str, Any]]:
    amount_positions = {
        amount: index
        for index, amount in enumerate(tested_amounts)
    }

    grouped: dict[
        tuple[Any, ...],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        amount = int(row.get("amount", 0))

        if amount not in amount_positions:
            continue

        key = (
            row.get("product_code"),
            int(row.get("term", 0)),
            row.get("payment_code"),
            round(float(row.get("rate", 0)), 4),
            bool(row.get("replenishment", False)),
            bool(row.get("partial_withdrawal", False)),
        )

        grouped[key].append(row)

    result: list[dict[str, Any]] = []

    for group_rows in grouped.values():
        sorted_rows = sorted(
            group_rows,
            key=lambda row: amount_positions[
                int(row["amount"])
            ],
        )

        block: list[dict[str, Any]] = []

        for row in sorted_rows:
            if not block:
                block = [row]
                continue

            previous_amount = int(block[-1]["amount"])
            current_amount = int(row["amount"])

            are_neighbours = (
                amount_positions[current_amount]
                == amount_positions[previous_amount] + 1
            )

            if are_neighbours:
                block.append(row)
            else:
                result.append(
                    _make_vtb_range_row(block)
                )
                block = [row]

        if block:
            result.append(
                _make_vtb_range_row(block)
            )

    return sorted(
        result,
        key=lambda row: (
            row["section"],
            row["product_name"],
            row["term_from"],
            row["amount_from"],
            -row["rate"],
        ),
    )


# ============================================================
# РОССЕЛЬХОЗБАНК
# ============================================================

def _normalise_rshb_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for row in rows:
        try:
            min_sum = int(row["min_sum"])
            max_sum = int(row["max_sum"])
            min_days = int(row["min_days"])
            max_days = int(row["max_days"])
            rate = round(float(row["rate"]), 4)

            product_name = str(
                row.get(
                    "deposit_name",
                    "Без названия",
                )
            ).strip()

            monthly = bool(
                row.get(
                    "monthly_interest_payment",
                    False,
                )
            )

            for term in RSHB_CONTROL_TERMS:
                if min_days <= term <= max_days:
                    result.append(
                        {
                            "bank": "Россельхозбанк",
                            "section": "Депозиты",
                            "product_name": product_name,
                            "amount_from": min_sum,
                            "amount_to": max_sum,
                            "term_from": term,
                            "term_to": term,
                            "payment_name": (
                                "Ежемесячно"
                                if monthly
                                else "В конце срока"
                            ),
                            "rate": rate,
                            "replenishment": bool(
                                row.get(
                                    "replenished",
                                    False,
                                )
                            ),
                            "partial_withdrawal": bool(
                                row.get(
                                    "partial_withdrawal",
                                    False,
                                )
                            ),
                        }
                    )

        except (KeyError, TypeError, ValueError):
            continue

    return result


def _merge_equal_terms(
    rows: list[dict[str, Any]],
    control_terms: list[int],
) -> list[dict[str, Any]]:
    positions = {
        term: index
        for index, term in enumerate(control_terms)
    }

    grouped: dict[
        tuple[Any, ...],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        key = (
            row["product_name"],
            row["amount_from"],
            row["amount_to"],
            row["payment_name"],
            row["rate"],
            row["replenishment"],
            row["partial_withdrawal"],
        )

        grouped[key].append(row)

    result: list[dict[str, Any]] = []

    for group_rows in grouped.values():
        sorted_rows = sorted(
            group_rows,
            key=lambda row: positions.get(
                int(row["term_from"]),
                999,
            ),
        )

        current = dict(sorted_rows[0])

        for row in sorted_rows[1:]:
            current_term = int(current["term_to"])
            next_term = int(row["term_from"])

            current_position = positions.get(current_term)
            next_position = positions.get(next_term)

            if (
                current_position is not None
                and next_position == current_position + 1
            ):
                current["term_to"] = next_term
            else:
                result.append(current)
                current = dict(row)

        result.append(current)

    return result


def _merge_touching_amount_ranges(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[Any, ...],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        key = (
            row["product_name"],
            row["term_from"],
            row["term_to"],
            row["payment_name"],
            row["rate"],
            row["replenishment"],
            row["partial_withdrawal"],
        )

        grouped[key].append(row)

    result: list[dict[str, Any]] = []

    for group_rows in grouped.values():
        sorted_rows = sorted(
            group_rows,
            key=lambda row: (
                int(row["amount_from"]),
                int(row["amount_to"]),
            ),
        )

        current = dict(sorted_rows[0])

        for row in sorted_rows[1:]:
            current_to = int(current["amount_to"])
            next_from = int(row["amount_from"])

            if next_from <= current_to + 1:
                current["amount_to"] = max(
                    current_to,
                    int(row["amount_to"]),
                )
            else:
                result.append(current)
                current = dict(row)

        result.append(current)

    return result


def build_rshb_ranges(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalised = _normalise_rshb_rows(rows)

    unique = _remove_exact_duplicates(
        normalised,
        (
            "product_name",
            "amount_from",
            "amount_to",
            "term_from",
            "term_to",
            "payment_name",
            "rate",
            "replenishment",
            "partial_withdrawal",
        ),
    )

    merged_terms = _merge_equal_terms(
        unique,
        RSHB_CONTROL_TERMS,
    )

    merged_amounts = _merge_touching_amount_ranges(
        merged_terms
    )

    final_rows = _remove_exact_duplicates(
        merged_amounts,
        (
            "product_name",
            "amount_from",
            "amount_to",
            "term_from",
            "term_to",
            "payment_name",
            "rate",
            "replenishment",
            "partial_withdrawal",
        ),
    )

    return sorted(
        final_rows,
        key=lambda row: (
            row["product_name"],
            row["payment_name"],
            row["amount_from"],
            row["term_from"],
            -row["rate"],
        ),
    )


# ============================================================
# СБЕРБАНК
# ============================================================

def _make_sber_range_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first = rows[0]

    amounts = sorted(
        int(row["amount"])
        for row in rows
    )

    return {
        "bank": "Сбербанк",
        "section": str(
            first.get(
                "section",
                "Срочные депозиты",
            )
        ),
        "product_code": str(
            first.get("product_code", "")
        ),
        "product_name": str(
            first.get("product_name", "")
        ),
        "amount_from": amounts[0],
        "amount_to": amounts[-1],
        "term_from": int(
            first.get("term", 0)
        ),
        "term_to": int(
            first.get("term", 0)
        ),
        "payment_name": "В конце срока",
        "rate": round(
            float(first.get("rate", 0)),
            4,
        ),
        "replenishment": (
            str(first.get("product_code", ""))
            == "Pop"
        ),
        "partial_withdrawal": (
            str(first.get("product_code", ""))
            == "Otz"
        ),
    }


def build_sber_amount_ranges(
    rows: list[dict[str, Any]],
    tested_amounts: list[int],
) -> list[dict[str, Any]]:
    amount_positions = {
        amount: index
        for index, amount in enumerate(tested_amounts)
    }

    grouped: dict[
        tuple[Any, ...],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        if not bool(row.get("is_active", False)):
            continue

        amount = int(row.get("amount", 0))

        if amount not in amount_positions:
            continue

        key = (
            row.get("product_type_code"),
            row.get("product_code"),
            row.get("product_name"),
            row.get("section"),
            int(row.get("term", 0)),
            round(float(row.get("rate", 0)), 4),
        )

        grouped[key].append(row)

    result: list[dict[str, Any]] = []

    for group_rows in grouped.values():
        sorted_rows = sorted(
            group_rows,
            key=lambda row: amount_positions[
                int(row["amount"])
            ],
        )

        block: list[dict[str, Any]] = []

        for row in sorted_rows:
            if not block:
                block = [row]
                continue

            previous_amount = int(block[-1]["amount"])
            current_amount = int(row["amount"])

            are_neighbours = (
                amount_positions[current_amount]
                == amount_positions[previous_amount] + 1
            )

            if are_neighbours:
                block.append(row)
            else:
                result.append(
                    _make_sber_range_row(block)
                )
                block = [row]

        if block:
            result.append(
                _make_sber_range_row(block)
            )

    return sorted(
        result,
        key=lambda row: (
            row["section"],
            row["product_name"],
            row["term_from"],
            row["amount_from"],
            -row["rate"],
        ),
    )