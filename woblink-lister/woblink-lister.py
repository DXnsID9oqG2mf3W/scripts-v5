import os
import re
import requests
import base64
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import argparse
from pathlib import Path
import sys
import io
import logging
from colorama import init, Fore, Style
import json
import time
import shutil

# Inicjalizacja colorama (reset kolorów)
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

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)
def sanitize_login_for_filename(login):
    return re.sub(r'[^a-zA-Z0-9_]', '_', login)

def all_covers_loaded(page, selector, login_email):
    items = page.query_selector_all(selector)
    for item in items:
        img_element = item.query_selector("img.v-lazy-image")
        src = img_element.get_attribute("src") if img_element else ""
        if not src or not re.match(r"^https?://", src):
            return False
    return True

def scroll_to_bottom(page, login_email, scroll_step=400, sleep_time=0.3, max_scrolls=100):
    logging.info(f"({login_email}) Odpoczywam sekundę po załadowaniu strony z wynikami...")
    time.sleep(1.0)
    last_height = 0
    scroll_count = 0
    for attempt in range(max_scrolls):
        page.evaluate(f"window.scrollBy(0, {scroll_step})")
        time.sleep(sleep_time)
        current_height = page.evaluate("document.body.scrollHeight")
        scroll_count += 1
        if current_height == last_height:
            logging.info(f"({login_email}) Osiągnięto koniec strony przy scrollowaniu ({attempt+1} scrolli, scrollHeight={current_height})")
            break
        last_height = current_height
    else:
        logging.warning(f"({login_email}) Maksymalna liczba scrolli ({max_scrolls}) osiągnięta – możliwe, że coś poszło nie tak.")
    return scroll_count

def process_section(page, section_name, login_email=""):
    def get_items():
        container_selector = "section.user-page__shelflist"
        ebook_item_selector = f"{container_selector} .shelflist-item"
        items = page.query_selector_all(ebook_item_selector)
        result = []
        warnings = []
        total = len(items)
        for idx, item in enumerate(items):
            try:
                title_element = item.query_selector("h3.shelflist-item__title")
                author_element = item.query_selector("p.shelflist-item__author")
                img_element = item.query_selector("img.v-lazy-image")
                title = title_element.inner_text().strip() if title_element else ""
                author = author_element.inner_text().strip() if author_element else ""
                cover = img_element.get_attribute("src") if img_element else ""
                is_bad = False
                if not cover or not re.match(r"^https?://", cover):
                    logging.warning(f"({login_email}) [{idx+1}/{total}] {section_name}: Brak załadowanej okładki dla: {author} | {title} | src: {cover}")
                    is_bad = True
                elif "placeholder" in cover:
                    logging.warning(f"({login_email}) [{idx+1}/{total}] {section_name}: Okładka placeholder: {author} | {title} | src: {cover}")
                    is_bad = True
                else:
                    logging.info(f"({login_email}) [{idx+1}/{total}] {section_name}: OK: {author} | {title}")
                result.append({
                    "author": author,
                    "title": title,
                    "cover": cover,
                })
                if is_bad:
                    warnings.append(idx)
            except Exception as e:
                logging.error(f"({login_email}) Błąd przy pobieraniu okładki: {e}")
        return result, warnings

    items_found = []
    try:        
        menu_selector = ".user-page__shelflist_filters > .user-page__shelflist_filters-menu"
        tab_selector = f"{menu_selector} li:has-text('{section_name}')"
        logging.info(f"({login_email}) Szukam zakładki '{section_name}'.")
        page.wait_for_selector(tab_selector, timeout=20000)
        tab = page.query_selector(tab_selector)
        if not tab:
            logging.error(f"({login_email}) Nie znaleziono zakładki '{section_name}'.")
            return items_found

        tab.click()
        logging.info(f"({login_email}) Klikam w zakładkę '{section_name}'.")
        page.wait_for_selector("div.loader", state="visible", timeout=60000)
        page.wait_for_selector("div.loader", state="hidden", timeout=60000)
        
        logging.info(f"({login_email}) Przewijam do końca sekcję '{section_name}' żeby załadować wszystkie okładki.")
        scroll_count = scroll_to_bottom(page, login_email)
        items_found, warnings = get_items()
        logging.info(f"({login_email}) Znaleziono {len(items_found)} pozycji po przewinięciu do końca strony.")

        if warnings:
            logging.info(f"({login_email}) Są niezaładowane okładki – przewijam ponownie {scroll_count}x.")
            for _ in range(scroll_count):
                page.evaluate(f"window.scrollBy(0, 400)")
                time.sleep(0.3)
            items_found, warnings = get_items()
            if warnings:
                logging.warning(f"({login_email}) Po powtórnym przewinięciu {len(warnings)} okładek nadal niezaładowanych. Akceptuję to co jest.")

    except Exception as e:
        logging.error(f"({login_email}) Błąd przy przetwarzaniu sekcji {section_name}: {e}")
    return items_found

def login(page, email, password):
    login_url = 'https://woblink.com/logowanie'
    logging.info(f"Przechodzę do strony logowania: {login_url}")
    try:
        page.goto(login_url, wait_until='domcontentloaded')
    except Exception as e:
        logging.error(f"Nie udało się załadować strony logowania {login_url}: {e}")
        raise
    try:
        cookie_button = page.wait_for_selector('button#CybotCookiebotDialogBodyButtonDecline', timeout=10000)
        cookie_button.click()
    except Exception as e:
        logging.warning(f"Przycisk cookies nie został znaleziony lub nie można go kliknąć: {e}")
    try:
        logging.info("Wypełniam dane logowania.")
        page.fill('input[name="_username"]', email)
        page.fill('input[name="_password"]', password)
        page.click('#login-form-submit')
    except Exception as e:
        logging.error(f"Błąd przy wysyłaniu formularza logowania: {e}")
        raise

def go_to_shelf(page):
    if "/account/moja-polka" not in page.url:
        logging.info("Przechodzę do strony '/account/moja-polka'.")
        page.goto("https://woblink.com/account/moja-polka", wait_until="domcontentloaded")
    logging.info("Czekam na pojawienie się loadera.")
    page.wait_for_selector("div.loader", state="visible", timeout=60000)
    logging.info("Czekam na ukrycie loadera.")
    page.wait_for_selector("div.loader", state="hidden", timeout=60000)

def accept_regulations(page):
    logging.info("Czekam na popup z regulaminem.")
    try:
        popup = page.wait_for_selector("#nw_popup_regulations", timeout=10000)
        if popup:
            logging.info("Popup z regulaminem znaleziony, akceptuję regulamin.")
            page.click("#nw_popup_regulations_checkbox + span.checkmark")
            page.click("#nw_popup_regulations_button")
            page.wait_for_selector("#nw_popup_regulations", state="detached", timeout=10000)
    except Exception as e:
        logging.info("Popup z regulaminem nie został znaleziony lub już został obsłużony.")

def count_broken_covers_json(data):
    broken = []
    resources = data.get("resources", {})
    for section in ["ebooks", "audiobooks"]:
        for idx, item in enumerate(resources.get(section, {}).get("items", [])):
            cover = item.get("cover", "")
            if cover and (not re.match(r"^https?://", cover)):
                broken.append({
                    "section": section,
                    "idx": idx + 1,
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "cover": cover,
                })
    return len(broken), broken

def count_broken_covers(json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    return count_broken_covers_json(data)

def process_login(email, password, output_dir, headless=False, output_path=None, login_email=None):
    ebook_items = []
    audiobook_items = []
    login_email = login_email or email

    with sync_playwright() as playwright:
        try:
            logging.info(f"=== Przetwarzam konto: {login_email} ===")
            logging.info("Uruchamiam przeglądarkę...")
            browser = playwright.chromium.launch(channel="chrome", headless=headless)
            context = browser.new_context()
            page = context.new_page()

            logging.info("Próba logowania...")
            login(page, email, password)
            accept_regulations(page)
            logging.info("Przechodzę do dashboardu użytkownika...")
            page.goto("https://woblink.com/account/dashboard", wait_until="domcontentloaded")

            product_count = 0
            try:
                logging.info("Sprawdzam liczbę zakupionych produktów na dashboardzie.")
                shelf_tile_selector = ".user-page__tile.user-page__tile--shelf h3"
                page.wait_for_selector(shelf_tile_selector, timeout=10000)
                product_count_text = page.query_selector(shelf_tile_selector).inner_text().strip()
                try:
                    product_count = int(product_count_text)
                    logging.info(f"Zakupione produkty: {product_count}")
                except ValueError:
                    logging.error(f"Nie udało się zinterpretować liczby zakupionych produktów: '{product_count_text}'")
                    product_count = 0
            except Exception as e:
                logging.error(f"Błąd podczas sprawdzania liczby zakupionych produktów: {e}")
                product_count = 0

            if product_count == 0:
                logging.warning("Brak zakupionych produktów. Pomiń pobieranie półki.")
            else:
                logging.info("Przechodzę do półki użytkownika...")
                go_to_shelf(page)

                logging.info("Przetwarzam sekcję 'EBooki'.")
                ebook_items = process_section(page, "EBooki", login_email=login_email)
                logging.info(f"Znaleziono {len(ebook_items)} pozycji w sekcji 'EBooki'.")

                logging.info("Przetwarzam sekcję 'Audiobooki'.")
                audiobook_items = process_section(page, "Audiobooki", login_email=login_email)
                logging.info(f"Znaleziono {len(audiobook_items)} pozycji w sekcji 'Audiobooki'.")
            
        except Exception as e:
            logging.exception(f"Napotkano nieoczekiwany błąd: {e}")
        finally:
            logging.info("Zamykam przeglądarkę.")
            browser.close()
    
    summary_json = {
        "credentials": {
            "login": email,
            "password": password
        },
        "resources": {
            "ebooks": {
                "count": len(ebook_items),
                "items": ebook_items
            },
            "audiobooks": {
                "count": len(audiobook_items),
                "items": audiobook_items
            },
            "courses": {
                "count": 0,
                "items": []
            }
        }
    }

    n_bad, bad_list = count_broken_covers_json(summary_json)
    if n_bad:
        logging.warning(f"Po parsowaniu konta {login_email} wykryto {n_bad} książek z niepełnym URL do okładki:")
        for b in bad_list:
            logging.warning(f"  [{b['section']}] {b['title']} | {b['author']} | {b['cover']}")
    else:
        logging.info(f"Wszystkie okładki dla {login_email} mają pełny URL.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)
    logging.success(f"Zapisano wynik do {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Logowanie do woblink z poprawą okładek i wymuszaniem lazy loadingu przez scrollowanie.")
    parser.add_argument("--login", help="Dane logowania w formacie email:password", required=False)
    parser.add_argument("--credentials-file", help="Ścieżka do pliku z listą danych logowania", required=False)
    parser.add_argument("--log", help="Włącz logowanie", action="store_true")
    parser.add_argument("--head", help="Uruchom przeglądarkę w trybie widocznym", action="store_true")
    parser.add_argument("--output", help="Katalog docelowy na pliki json (domyślnie 'results_json')", required=False)
    parser.add_argument("--fix-covers", help="Wymuś ponowne przetwarzanie konta, jeśli są złe okładki (zastępuje plik, robi backup)", action="store_true")
    args = parser.parse_args()

    if not args.log:
        logging.disable(logging.CRITICAL)

    output_dir = Path(args.output) if args.output else Path("results_json")
    headless = not args.head

    def print_broken_summary(json_path, login):
        if not os.path.exists(json_path):
            logging.info(f"Brak pliku: {json_path}")
            return 0
        n_bad, bad_list = count_broken_covers(json_path)
        if n_bad == 0:
            logging.info(f"({login}) Wszystkie okładki poprawne (pełny URL)")
        else:
            logging.warning(f"({login}) Liczba pozycji z niepoprawnymi okładkami: {n_bad}")
            for b in bad_list:
                logging.warning(f"    [{b['section']}] {b['title']} | {b['author']} | {b['cover']}")
        return n_bad

    credentials = []
    if args.login:
        credentials = [args.login]
    elif args.credentials_file:
        if not os.path.exists(args.credentials_file):
            logging.error(f"Plik {args.credentials_file} nie istnieje.")
            sys.exit(1)
        with open(args.credentials_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                credentials.append(line)
    else:
        logging.error("Podaj --login email:haslo LUB --credentials-file plik.txt")
        sys.exit(1)

    total = len(credentials)
    for idx, cred in enumerate(credentials, 1):
        try:
            email, password = cred.split(":", 1)
        except ValueError:
            continue
        safe_login = sanitize_login_for_filename(email)
        json_path = output_dir / f"shelf_{safe_login}.json"
        backup_path = output_dir / f"shelf_{safe_login}.backup"

        # --- Kolorowana sekcja [x/y] Konto: ... ---
        current_num = f"{Fore.GREEN}{idx}{Style.RESET_ALL}"
        total_num = f"{Fore.RED}{total}{Style.RESET_ALL}"
        prefix = f"{Style.BRIGHT}[{current_num}/{total_num}]{Style.RESET_ALL} Konto: {email}"
        logging.info(f"--- {prefix} ---")

        logging.info(f"{prefix} Sprawdzam czy istnieje plik: {json_path}")
        if json_path.exists():
            logging.info(f"{prefix} Plik istnieje: {json_path}")
            n_bad = print_broken_summary(json_path, email)
            if n_bad == 0:
                logging.info(f"{prefix} ({email}) Pomijam przetwarzanie konta – wszystko poprawne.")
            elif args.fix_covers:
                logging.info(f"{prefix} ({email}) Tworzę backup starego pliku: {backup_path}")
                shutil.copy2(json_path, backup_path)
                logging.info(f"{prefix} ({email}) Rozpoczynam naprawianie konta (fix), nadpisuję: {json_path}")
                process_login(email, password, output_dir, headless=headless, output_path=json_path, login_email=email)
            else:
                logging.warning(f"{prefix} ({email}) Są niepoprawne okładki, ale fix nie uruchomiony – pomijam.")
        else:
            logging.info(f"{prefix} Plik nie istnieje – rozpoczynam przetwarzanie konta {email}.")
            process_login(email, password, output_dir, headless=headless, output_path=json_path, login_email=email)

if __name__ == "__main__":
    main()
