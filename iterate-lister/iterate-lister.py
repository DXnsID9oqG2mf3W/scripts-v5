import argparse
import subprocess
import os
import logging
from datetime import datetime

# Ulepszony formatter z kolorami ANSI
class ColorFormatter(logging.Formatter):
    COLOR_DEBUG = "\x1b[90m"       # Jasny szary (dla DEBUG)
    COLOR_INFO = "\x1b[32m"        # Zielony (dla INFO)
    COLOR_WARNING = "\x1b[33m"     # Żółty (dla WARNING)
    COLOR_ERROR = "\x1b[31m"       # Czerwony (dla ERROR)
    COLOR_CRITICAL = "\x1b[1;31m"  # Pogrubiony czerwony (dla CRITICAL)
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: COLOR_DEBUG + "%(asctime)s - %(levelname)s - %(message)s" + RESET,
        logging.INFO: COLOR_INFO + "%(asctime)s - %(levelname)s - %(message)s" + RESET,
        logging.WARNING: COLOR_WARNING + "%(asctime)s - %(levelname)s - %(message)s" + RESET,
        logging.ERROR: COLOR_ERROR + "%(asctime)s - %(levelname)s - %(message)s" + RESET,
        logging.CRITICAL: COLOR_CRITICAL + "%(asctime)s - %(levelname)s - %(message)s" + RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.DEBUG])
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

def setup_logger(log_filename):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Handler dla konsoli z kolorowym formatowaniem
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)

    # Handler do pliku (bez kolorów)
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

def main():
    parser = argparse.ArgumentParser(
        description="Uruchamia *-lister.py dla każdej pary login:hasło z podanego pliku."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Ścieżka do pliku txt z danymi logowania (każda linia: login:hasło)"
    )
    parser.add_argument(
        "--script",
        required=True,
        help="Ścieżka do skryptu *-lister.py"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Ścieżka do katalogu, w którym zapisywane będą pliki wynikowe."
    )
    args = parser.parse_args()

    logger = setup_logger("iterate-lister.log")

    # Sprawdzenie, czy plik z danymi logowania istnieje
    if not os.path.exists(args.file):
        logger.error(f"Plik {args.file} nie istnieje!")
        return

    # Jeśli katalog wyjściowy nie istnieje, tworzymy go
    if not os.path.isdir(args.output):
        logger.info(f"Katalog {args.output} nie istnieje. Tworzę katalog...")
        os.makedirs(args.output)

    # Wczytanie i filtrowanie danych logowania
    with open(args.file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    valid_lines = []
    for line in lines:
        if ":" in line:
            valid_lines.append(line)
        else:
            logger.warning(f"Pominięto niepoprawny format: {line}")

    total_accounts = len(valid_lines)
    logger.info(f"Znaleziono {total_accounts} poprawnych kont do przetworzenia.")

    # Przetwarzanie poszczególnych kont
    for idx, line in enumerate(valid_lines, start=1):
        parts = line.split(":", 1)
        login = parts[0]
        output_filename = os.path.join(args.output, f"{login}.txt")

        # Jeśli plik już istnieje, pomijamy konto
        if os.path.exists(output_filename):
            logger.info(f"Konto {idx}/{total_accounts}: {line} pominięte, plik {output_filename} już istnieje.")
            continue

        logger.info(f"Przetwarzanie konta {idx}/{total_accounts}: {line}")
        start_time = datetime.now()

        # Budujemy polecenie do wykonania
        command = ["python", args.script, "--login", line]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        if result.returncode != 0:
            logger.error(f"Błąd przy przetwarzaniu konta {idx}/{total_accounts} ({line}). Czas: {elapsed_time:.2f}s\n{result.stderr}")
        else:
            output = result.stdout
            with open(output_filename, "w", encoding="utf-8") as out_file:
                out_file.write(line + "\n\n")
                out_file.write(output)
            logger.info(f"Konto {idx}/{total_accounts} przetworzone w {elapsed_time:.2f}s, wynik zapisany do pliku: {output_filename}")

if __name__ == "__main__":
    main()
