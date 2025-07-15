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

# Kolorowe logi
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
    return re.sub(r'[^a-zA-Z0-9_]', '_', login)

def login(page, email, password):
    login_url = 'https://helion.pl/users/login'
    logging.info(f"Przechodzę do strony logowania: {login_url}")
    page.goto(login_url, wait_until='domcontentloaded')
    try:
        if page.is_visible('button#CybotCookiebotDialogBodyButtonDecline'):
            page.click('button#CybotCookiebotDialogBodyButtonDecline')
    except Exception as e:
        logging.debug(f"Brak przycisku cookies lub nie można kliknąć: {e}")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('#log_in_submit')
    page.wait_for_load_state("domcontentloaded")
    time.sleep(1)

def go_to_biblioteka(page, kind):
    url = f"https://helion.pl/users/konto/biblioteka/{kind}"
    logging.info(f"Przechodzę do: {url}")
    page.goto(url, wait_until='domcontentloaded')
    time.sleep(1)

def get_books(page):
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

def process_login(email, password, output_dir, headless, output_path):
    ebooks, audiobooks, courses = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            logging.info(f"Loguję: {email}")
            login(page, email, password)
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

def load_credentials(args):
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
    parser = argparse.ArgumentParser(
        description="helion-lister - eksport półek (ebooki/audiobooki/kursy) do JSON, styl woblink-lister"
    )
    parser.add_argument("--login", help="email:haslo", required=False)
    parser.add_argument("--credentials-file", help="Plik z loginami email:haslo", required=False)
    parser.add_argument("--output", help="Katalog wyników (domyślnie results_json)", required=False)
    parser.add_argument("--log", help="Pokaż logi", action="store_true")
    parser.add_argument("--head", help="Uruchom przeglądarkę z GUI (widoczne klikanie, domyślnie headless)", action="store_true")

    # Jeśli nie podano żadnych argumentów - pokaż pomoc
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if not args.log:
        logging.disable(logging.CRITICAL)

    output_dir = Path(args.output) if args.output else Path("results_json")
    headless = not args.head

    credentials = load_credentials(args)
    # Jeśli podano inne flagi, ale NIE podano loginu ani credentials-file, wyświetl czytelną podpowiedź i help.
    if not credentials:
        print(
            f"{Fore.YELLOW}Musisz podać login (--login email:haslo) lub plik z loginami (--credentials-file plik.txt).{Style.RESET_ALL}\n"
        )
        parser.print_help()
        sys.exit(1)

    total = len(credentials)
    for idx, cred in enumerate(credentials, 1):
        try:
            email, password = cred.split(":", 1)
        except ValueError:
            logging.warning(f"Pominięto błędny wiersz: {cred}")
            continue
        safe_login = sanitize_login_for_filename(email)
        output_path = output_dir / f"shelf_{safe_login}.json"
        current_num = f"{Fore.GREEN}{idx}{Style.RESET_ALL}"
        total_num = f"{Fore.RED}{total}{Style.RESET_ALL}"
        prefix = f"{Style.BRIGHT}[{current_num}/{total_num}]{Style.RESET_ALL} Konto: {email}"
        logging.info(f"--- {prefix} ---")
        process_login(email, password, output_dir, headless, output_path)

if __name__ == "__main__":
    main()
