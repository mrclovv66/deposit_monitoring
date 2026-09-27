from __future__ import annotations

import mimetypes
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _get_required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"В файле .env не заполнено поле {name}"
        )

    return value


def send_reports_email(
    attachments: list[Path],
) -> None:
    smtp_host = _get_required_setting("SMTP_HOST")
    smtp_port = int(
        _get_required_setting("SMTP_PORT")
    )
    sender_email = _get_required_setting(
        "SMTP_EMAIL"
    )
    smtp_password = _get_required_setting(
        "SMTP_PASSWORD"
    )
    recipient_email = _get_required_setting(
        "EMAIL_TO"
    )

    existing_files = [
        path
        for path in attachments
        if path.exists() and path.is_file()
    ]

    if not existing_files:
        raise FileNotFoundError(
            "Не найдено ни одного PDF для отправки"
        )

    if len(existing_files) != len(attachments):
        missing_files = [
            str(path)
            for path in attachments
            if not path.exists()
        ]

        raise FileNotFoundError(
            "Не найдены PDF-файлы: "
            + ", ".join(missing_files)
        )

    current_date = datetime.now()

    message = EmailMessage()

    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = (
        "Депозитные ставки для юридических лиц — "
        f"{current_date:%d.%m.%Y}"
    )

    message.set_content(
        "Здравствуйте!\n\n"
        "Во вложении актуальные депозитные ставки "
        "для юридических лиц:\n\n"
        "• ВТБ\n"
        "• Россельхозбанк\n"
        "• Сбербанк\n\n"
        f"Дата формирования отчётов: "
        f"{current_date:%d.%m.%Y %H:%M}.\n\n"
        "Письмо сформировано автоматически."
    )

    for file_path in existing_files:
        mime_type, _ = mimetypes.guess_type(
            file_path.name
        )

        if mime_type:
            main_type, sub_type = mime_type.split(
                "/",
                maxsplit=1,
            )
        else:
            main_type = "application"
            sub_type = "pdf"

        with file_path.open("rb") as file:
            message.add_attachment(
                file.read(),
                maintype=main_type,
                subtype=sub_type,
                filename=file_path.name,
            )

    with smtplib.SMTP_SSL(
        host=smtp_host,
        port=smtp_port,
        timeout=60,
    ) as smtp:
        smtp.login(
            sender_email,
            smtp_password,
        )

        smtp.send_message(message)

    print(
        "Письмо успешно отправлено на "
        f"{recipient_email}"
    )