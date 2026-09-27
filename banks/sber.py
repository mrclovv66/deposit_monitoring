from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings(
    "ignore",
    category=InsecureRequestWarning,
)

API_URL = (
    "https://www.sberbank.ru/proxy/services/"
    "corp-deposit-calculator/deposits"
)


@dataclass(frozen=True)
class SberProduct:
    product_type_code: str
    product_code: str
    product_name: str
    section: str


@dataclass(frozen=True)
class SberDepositRate:
    bank: str
    product_type_code: str
    product_code: str
    product_name: str
    section: str
    amount: int
    term: int
    client_type: int
    operation_date: str
    is_active: bool
    rate: float
    income: float


SBER_PRODUCTS = (
    SberProduct(
        product_type_code="Dep",
        product_code="Classic",
        product_name="Депозит без пополнения и снятия",
        section="Срочные депозиты",
    ),
    SberProduct(
        product_type_code="Dep",
        product_code="Otz",
        product_name="Депозит со снятием",
        section="Срочные депозиты",
    ),
    SberProduct(
        product_type_code="Dep",
        product_code="Pop",
        product_name="Депозит с пополнением",
        section="Срочные депозиты",
    ),
    SberProduct(
        product_type_code="NSO",
        product_code="NSO",
        product_name="Неснижаемый остаток",
        section="Неснижаемый остаток",
    ),
)


def _parse_response(
    data: Any,
    product: SberProduct,
    amount: int,
    term: int,
    client_type: int,
    operation_date: str,
) -> SberDepositRate:
    if not isinstance(data, dict):
        raise RuntimeError(
            "Сбер вернул неожиданный формат ответа: "
            f"{type(data).__name__}"
        )

    response_product_code = str(
        data.get(
            "productCode",
            product.product_code,
        )
    )

    response_product_type = str(
        data.get(
            "productTypeCode",
            product.product_type_code,
        )
    )

    return SberDepositRate(
        bank="Сбербанк",
        product_type_code=response_product_type,
        product_code=response_product_code,
        product_name=product.product_name,
        section=product.section,
        amount=amount,
        term=term,
        client_type=client_type,
        operation_date=operation_date,
        is_active=bool(
            data.get(
                "isActive",
                False,
            )
        ),
        rate=float(
            data.get(
                "rate",
                0,
            )
        ),
        income=float(
            data.get(
                "income",
                0,
            )
        ),
    )


def get_sber_rate(
    product: SberProduct,
    amount: int,
    term: int,
    client_type: int = 1,
    operation_date: str | None = None,
) -> SberDepositRate:
    """
    Получает ставку по одному продукту Сбербанка.

    client_type:
    1 — ООО / юридическое лицо.
    """

    if amount <= 0:
        raise ValueError(
            "Сумма должна быть больше нуля"
        )

    if term <= 0:
        raise ValueError(
            "Срок должен быть больше нуля"
        )

    if client_type <= 0:
        raise ValueError(
            "ClientType должен быть больше нуля"
        )

    request_date = (
        operation_date
        if operation_date is not None
        else date.today().isoformat()
    )

    params = {
        "OperationDate": request_date,
        "Currency": "RUB",
        "ProductTypeCode": product.product_type_code,
        "ProductCode": product.product_code,
        "Amount": amount,
        "Term": term,
        "ClientType": client_type,
    }

    response = requests.get(
        API_URL,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.sberbank.ru/",
        },
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    return _parse_response(
        data=response.json(),
        product=product,
        amount=amount,
        term=term,
        client_type=client_type,
        operation_date=request_date,
    )


def get_sber_rates(
    amount: int,
    term: int,
    client_type: int = 1,
    operation_date: str | None = None,
) -> list[SberDepositRate]:
    """
    Запрашивает все нужные продукты Сбербанка.
    Ошибка одного продукта не останавливает остальные.
    """

    rates: list[SberDepositRate] = []
    errors: list[str] = []

    for product in SBER_PRODUCTS:
        try:
            rate = get_sber_rate(
                product=product,
                amount=amount,
                term=term,
                client_type=client_type,
                operation_date=operation_date,
            )

            rates.append(rate)

        except Exception as error:
            errors.append(
                f"{product.product_name}: {error}"
            )

    if not rates:
        error_text = "; ".join(errors)

        raise RuntimeError(
            "Не удалось получить ни одного "
            f"продукта Сбербанка. {error_text}"
        )

    return sorted(
        rates,
        key=lambda row: (
            not row.is_active,
            row.section,
            -row.rate,
            row.product_name,
        ),
    )