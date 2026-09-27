from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from email_sender import send_reports_email


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"


def run_main_program() -> None:
    main_file = PROJECT_DIR / "main.py"

    if not main_file.exists():
        raise FileNotFoundError(
            f"Не найден файл: {main_file}"
        )

    print("Запускаем сбор банковских ставок...")

    result = subprocess.run(
        [
            sys.executable,
            str(main_file),
        ],
        cwd=PROJECT_DIR,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "main.py завершился с ошибкой. "
            f"Код завершения: {result.returncode}"
        )


def get_report_files() -> list[Path]:
    current_date = datetime.now().strftime(
        "%d-%m-%Y"
    )

    report_files = [
        OUTPUT_DIR
        / f"ВТБ_ставки_{current_date}.pdf",

        OUTPUT_DIR
        / f"РСХБ_ставки_{current_date}.pdf",

        OUTPUT_DIR
        / f"Сбербанк_ставки_{current_date}.pdf",
    ]

    missing_files = [
        path
        for path in report_files
        if not path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "После выполнения main.py не найдены файлы:\n"
            + "\n".join(
                str(path)
                for path in missing_files
            )
        )

    return report_files


def main() -> None:
    print("=" * 80)
    print("ЕЖЕНЕДЕЛЬНЫЙ СБОР И ОТПРАВКА ОТЧЁТОВ")
    print("=" * 80)

    run_main_program()

    report_files = get_report_files()

    print()
    print("Отправляем письмо с файлами:")

    for file_path in report_files:
        print(f"- {file_path.name}")

    send_reports_email(report_files)

    print()
    print("Задача успешно завершена.")


if __name__ == "__main__":
    main()
    