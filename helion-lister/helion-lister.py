import os
import re
import sys
import io
import json
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from colorama import init, Fore, Style
import logging

# --- Kolorowe logi na konsolę (logi INFO, WARNING, ERROR itp. są kolorowe dla czytelności)
init(autoreset=True)

SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")
def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)
logging.Logger.success = success
logging.success = logging.getLogger().success

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.YELLOW,
        'SUCCESS': Fore.GREEN,
        'WARNING': Fore.MAGENTA,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        return super().format(record)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.DEBUG, handlers=[handler])
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def sanitize_login_for_filename(login):
    """ Zamienia znaki niemożliwe do użycia w nazwach plików na podkreślenia """
    return re.sub(r'[^a-zA-Z0-9_]', '_', login)

def login(page, email, password):
    """ Loguje do Heliona, zwraca True/False. Sprawdza obecność tekstu powitalnego. """
    login_url = 'https://helion.pl/users/login'
    logging.info(f"Przechodzę do strony logowania: {login_url}")
    page.goto(login_url, wait_until='domcontentloaded')
    # Kliknij "odrzuć cookies" jeśli jest widoczny przycisk
    try:
        if page.is_visible('button#CybotCookiebotDialogBodyButtonDecline'):
            page.click('button#CybotCookiebotDialogBodyButtonDecline')
    except Exception as e:
        logging.debug(f"Brak przycisku cookies lub nie można kliknąć: {e}")
    # Uzupełnij dane logowania
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('#log_in_submit')
    page.wait_for_load_state("domcontentloaded")
    welcome_text = "Witaj w Twoim koncie"
    try:
        # Poczekaj do 7 sekund na tekst powitalny (sprawdzenie czy logowanie udane)
        page.wait_for_selector(f"text={welcome_text}", timeout=7000)
        logging.success("Zalogowano pomyślnie.")
        return True
    except Exception as e:
        logging.error(f"Nie zalogowano! Nie znaleziono tekstu powitalnego \"{welcome_text}\" dla {email}")
        return False

def go_to_biblioteka(page, kind):
    """ Przechodzi do danej półki: ebooki, audiobooki, kursy """
    url = f"https://helion.pl/users/konto/biblioteka/{kind}"
    logging.info(f"Przechodzę do: {url}")
    page.goto(url, wait_until='domcontentloaded')
    time.sleep(1)  # Mały sleep by mieć pewność że treść się pojawi

def get_books(page):
    """ Zbiera książki z obecnie widocznej półki (ebooki, audiobooki, kursy) """
    items = page.query_selector_all('ul#listBooks li')
    result = []
    for item in items:
        try:
            title_el = item.query_selector('h3.title')
            author_el = item.query_selector('p.author')
            img_el = item.query_selector('img')
            title = title_el.inner_text().strip() if title_el else ""
            author = author_el.inner_text().strip() if author_el else ""
            cover = img_el.get_attribute('src') if img_el else ""
            if not cover and img_el and img_el.get_attribute('data-src'):
                cover = img_el.get_attribute('data-src')
            result.append({
                "author": author,
                "title": title,
                "cover": cover,
            })
        except Exception as e:
            logging.warning(f"Błąd przy przetwarzaniu pozycji: {e}")
    return result

def process_login(email, password, output_dir, headless, output_path, return_login_status=False):
    """ Przetwarza jedno konto: loguje, eksportuje półki, zapisuje wynik do pliku """
    ebooks, audiobooks, courses = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            logging.info(f"Loguję: {email}")
            ok = login(page, email, password)
            if not ok:
                logging.error(f"Przerwano, nie udało się zalogować do konta {email}.")
                return False if return_login_status else None
            # Eksport każdej półki
            go_to_biblioteka(page, "ebooki")
            ebooks = get_books(page)
            go_to_biblioteka(page, "audiobooki")
            audiobooks = get_books(page)
            go_to_biblioteka(page, "kursy")
            courses = get_books(page)
        except Exception as e:
            logging.error(f"Błąd przy przetwarzaniu konta: {e}")
        finally:
            browser.close()
    # Zapisz wynik do JSON
    summary_json = {
        "credentials": {"login": email, "password": password},
        "resources": {
            "ebooks": {"count": len(ebooks), "items": ebooks},
            "audiobooks": {"count": len(audiobooks), "items": audiobooks},
            "courses": {"count": len(courses), "items": courses},
        }
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)
    logging.success(f"Zapisano wynik do {output_path}")
    return True if return_login_status else None

def load_credentials(args):
    """ Ładuje listę loginów z pliku lub flagi --login """
    credentials = []
    if args.login:
        if ':' not in args.login:
            logging.error("--login musi być w formacie email:haslo")
            sys.exit(1)
        credentials = [args.login]
    elif args.credentials_file:
        if not os.path.isfile(args.credentials_file):
            logging.error(f"Plik {args.credentials_file} nie istnieje.")
            sys.exit(1)
        with open(args.credentials_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    credentials.append(line)
    return credentials

def main():
    # --- Argumenty programu
    parser = argparse.ArgumentParser(
        description="helion-lister - eksport półek (ebooki/audiobooki/kursy) do JSON, styl woblink-lister"
    )
    parser.add_argument("--login", help="email:haslo", required=False)
    parser.add_argument("--credentials-file", help="Plik z loginami email:haslo", required=False)
    parser.add_argument("--output", help="Katalog wyników (domyślnie results_json)", required=False)
    parser.add_argument("--log", help="Pokaż logi", action="store_true")
    parser.add_argument("--head", help="Uruchom przeglądarkę z GUI (widoczne klikanie, domyślnie headless)", action="store_true")

    # --- Pokaż pomoc, jeśli nie podano żadnych flag
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # --- Jeżeli nie podano --log, wyłącz logowanie poniżej ERROR
    if not args.log:
        logging.disable(logging.CRITICAL)

    output_dir = Path(args.output) if args.output else Path("results_json")
    headless = not args.head

    # --- Wczytaj login:haslo z flagi lub pliku
    credentials = load_credentials(args)
    if not credentials:
        print(
            f"{Fore.YELLOW}Musisz podać login (--login email:haslo) lub plik z loginami (--credentials-file plik.txt).{Style.RESET_ALL}\n"
        )
        parser.print_help()
        sys.exit(1)

    total = len(credentials)
    failed_attempts = []

    # --- Główna pętla przetwarzania kont
    for idx, cred in enumerate(credentials, 1):
        try:
            email, password = cred.split(":", 1)
        except ValueError:
            logging.warning(f"Pominięto błędny wiersz: {cred}")
            continue
        safe_login = sanitize_login_for_filename(email)
        output_path = output_dir / f"shelf_{safe_login}.json"
        # --- Pomijamy już przetworzone konta (nie nadpisujemy plików!)
        if output_path.exists():
            logging.info(f"Pomięto, już przetworzono ({output_path.name})")
            continue
        current_num = f"{Fore.GREEN}{idx}{Style.RESET_ALL}"
        total_num = f"{Fore.RED}{total}{Style.RESET_ALL}"
        prefix = f"{Style.BRIGHT}[{current_num}/{total_num}]{Style.RESET_ALL} Konto: {email}"
        logging.info(f"--- {prefix} ---")
        ok = process_login(email, password, output_dir, headless, output_path, return_login_status=True)
        if not ok:
            failed_attempts.append((email, password))

    # --- Ostatnia szansa dla nieudanych loginów (retry)
    if failed_attempts:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}OSTATNIA SZANSA: Ponawiam logowanie dla nieudanych kont...{Style.RESET_ALL}\n")
        for idx, (email, password) in enumerate(failed_attempts, 1):
            safe_login = sanitize_login_for_filename(email)
            output_path = output_dir / f"shelf_{safe_login}.json"
            # Jeszcze raz: pomijamy, jeśli konto już przetworzone w międzyczasie
            if output_path.exists():
                logging.info(f"(Retry) Pominięto, już przetworzono ({output_path.name})")
                continue
            prefix = f"{Style.BRIGHT}[retry {idx}/{len(failed_attempts)}]{Style.RESET_ALL} Konto: {email}"
            logging.info(f"--- {prefix} ---")
            ok = process_login(email, password, output_dir, headless, output_path, return_login_status=True)
            if not ok:
                logging.error(f"(Retry) Nadal nie udało się zalogować do konta {email}")

if __name__ == "__main__":
    main()
