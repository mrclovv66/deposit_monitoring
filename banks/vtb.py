from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning


API_URL = "https://www.vtb.ru/api/deposits/comparison"

# Скрываем предупреждение только потому, что для публичного API ВТБ
# ниже намеренно отключена проверка SSL-сертификата.
warnings.filterwarnings(
    "ignore",
    category=InsecureRequestWarning,
)


@dataclass(frozen=True)
class VTBDepositRate:
    product_id: str
    product_code: str
    is_active: bool
    rate: float
    income: float
    early_termination: bool
    capitalization: bool
    partial_withdrawal: bool
    replenishment: bool


def _find_products(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [
            item
            for item in data
            if isinstance(item, dict)
        ]

    if not isinstance(data, dict):
        return []

    likely_keys = (
        "products",
        "data",
        "result",
        "items",
        "deposits",
        "comparison",
        "offers",
    )

    for key in likely_keys:
        value = data.get(key)

        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

        if isinstance(value, dict):
            products = _find_products(value)

            if products:
                return products

    for value in data.values():
        if isinstance(value, (dict, list)):
            products = _find_products(value)

            if products:
                return products

    return []


def get_vtb_rates(
    amount: int,
    term: int,
    payment_code: str = "end",
    early_termination: bool = False,
) -> list[VTBDepositRate]:
    if amount <= 0:
        raise ValueError(
            "Сумма должна быть больше нуля"
        )

    if term <= 0:
        raise ValueError(
            "Срок должен быть больше нуля"
        )

    allowed_payment_codes = {
        "start",
        "monthly",
        "end",
    }

    if payment_code not in allowed_payment_codes:
        raise ValueError(
            "payment_code должен быть: "
            "'start', 'monthly' или 'end'"
        )

    payload = {
        "currencyCode": "RUB",
        "sum": amount,
        "term": term,
        "paymentCode": payment_code,
        "isEarlyTermination": early_termination,
        "projectSysName": "vtb.ru",
    }

    response = requests.post(
        API_URL,
        json=payload,
        headers={
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://www.vtb.ru",
            "Referer": "https://www.vtb.ru/",
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,

        # Только для публичного API ВТБ.
        verify=False,
    )

    response.raise_for_status()

    data: Any = response.json()
    products = _find_products(data)

    if not products:
        if isinstance(data, dict):
            raise RuntimeError(
                "ВТБ вернул объект, но список депозитов "
                "не найден. Поля ответа: "
                f"{list(data.keys())}"
            )

        raise RuntimeError(
            "ВТБ вернул ответ без списка депозитов"
        )

    rates: list[VTBDepositRate] = []

    for item in products:
        try:
            product_code = str(
                item.get("productCode", "")
            ).strip()

            if not product_code:
                continue

            rates.append(
                VTBDepositRate(
                    product_id=str(
                        item.get("productId", "")
                    ),
                    product_code=product_code,
                    is_active=bool(
                        item.get("isActive", False)
                    ),
                    rate=float(
                        item.get("betInPercent", 0)
                    ),
                    income=float(
                        item.get("income", 0)
                    ),
                    early_termination=bool(
                        item.get(
                            "isEarlyTermination",
                            False,
                        )
                    ),
                    capitalization=bool(
                        item.get(
                            "isPercentCapitalization",
                            False,
                        )
                    ),
                    partial_withdrawal=bool(
                        item.get(
                            "isPartialWithdrawal",
                            False,
                        )
                    ),
                    replenishment=bool(
                        item.get(
                            "isReplenishment",
                            False,
                        )
                    ),
                )
            )

        except (TypeError, ValueError):
            continue

    if not rates:
        raise RuntimeError(
            "Ответ ВТБ получен, но продукты "
            "не удалось преобразовать"
        )

    return sorted(
        rates,
        key=lambda row: (
            not row.is_active,
            -row.rate,
            row.product_code,
        ),
    )