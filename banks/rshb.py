from dataclasses import dataclass
from typing import Any

import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings(
    "ignore",
    category=InsecureRequestWarning,
)

API_URL = "https://www.rshb.ru/api/v1/depositrates/businessdepositrates"


@dataclass(frozen=True)
class DepositRate:
    bank: str
    deposit_name: str
    min_sum: int
    max_sum: int
    min_days: int
    max_days: int
    rate: float
    monthly_interest_payment: bool
    replenished: bool
    partial_withdrawal: bool


def _find_rates_list(payload: Any) -> list[dict[str, Any]]:
    """
    Находит список ставок, даже если API завернул его
    в объект вида data/result/items/content.
    """

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    common_keys = (
        "data",
        "result",
        "items",
        "rates",
        "content",
        "businessDepositRates",
    )

    for key in common_keys:
        value = payload.get(key)

        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

        if isinstance(value, dict):
            nested = _find_rates_list(value)
            if nested:
                return nested

    # Запасной рекурсивный поиск по любым полям.
    for value in payload.values():
        if isinstance(value, (dict, list)):
            nested = _find_rates_list(value)
            if nested:
                return nested

    return []


def get_rshb_rates() -> list[DepositRate]:
    response = requests.get(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.rshb.ru/business/deposits",
        },
        timeout=30,
        verify=False,
    )

    response.raise_for_status()
    payload: Any = response.json()

    raw_rates = _find_rates_list(payload)

    if not raw_rates:
        if isinstance(payload, dict):
            print("Поля ответа API:", list(payload.keys()))

        raise RuntimeError(
            "API РСХБ ответил, но список ставок в ответе не найден"
        )

    rates: list[DepositRate] = []

    for item in raw_rates:
        try:
            rates.append(
                DepositRate(
                    bank="Россельхозбанк",
                    deposit_name=str(
                        item.get("depositName")
                        or item.get("depositeName")
                        or "Без названия"
                    ),
                    min_sum=int(item["minSum"]),
                    max_sum=int(item["maxSum"]),
                    min_days=int(item["minDays"]),
                    max_days=int(item["maxDays"]),
                    rate=float(item["rate"]),
                    monthly_interest_payment=bool(
                        item.get("isMonthlyInterestPayment", False)
                    ),
                    replenished=bool(
                        item.get("isReplenished", False)
                    ),
                    partial_withdrawal=bool(
                        item.get("isPartialWithdrawal", False)
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            print("Пропущена некорректная запись:", item)
            print("Причина:", error)

    if not rates:
        raise RuntimeError(
            "Ответ РСХБ получен, но записи не удалось преобразовать"
        )

    return sorted(
        rates,
        key=lambda row: (
            row.deposit_name,
            row.min_sum,
            row.max_sum,
            row.min_days,
            row.max_days,
            row.rate,
        ),
    )