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

# Inicjalizacja colorama (zapewnia reset kolorów)
init(autoreset=True)

# Definicja niestandardowego poziomu logowania "SUCCESS"
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)

# Dodajemy metodę success do klasy Logger
logging.Logger.success = success
logging.success = logging.getLogger().success

# Definicja niestandardowego formatera kolorowanego
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
    # Zamienia wszystko oprócz liter, cyfr i _ na _
    return re.sub(r'[^a-zA-Z0-9_]', '_', login)

def process_section(page, section_name):
    """
    Funkcja przetwarza daną sekcję (np. "EBooki" lub "Audiobooki"):
      1. Czeka na kontener menu, szuka zakładki o podanej nazwie i klika w nią.
      2. Po kliknięciu czeka na pojawienie się loadera i jego ukrycie.
      3. Iteruje po elementach (div.shelflist-item) na bieżącej stronie.
         Jeśli lista elementów jest pusta, przerywa iterację.
      4. Jeśli dostępny jest przycisk ">" (next), klika go, czeka na loader,
         aż zniknie, i przetwarza kolejną stronę.
    Zwraca listę pozycji jako słowniki: author, title, cover.
    """
    items_found = []
    try:        
        # Czekamy na kontener menu i szukamy zakładki o danej nazwie
        menu_selector = ".user-page__shelflist_filters > .user-page__shelflist_filters-menu"
        tab_selector = f"{menu_selector} li:has-text('{section_name}')"
        logging.info(f"Szukam zakładki '{section_name}'.")
        page.wait_for_selector(tab_selector, timeout=20000)
        tab = page.query_selector(tab_selector)
        if not tab:
            logging.error(f"Nie znaleziono elementu <li> zawierającego '{section_name}' w menu.")
            return items_found
        
        logging.info(f"Klikam w zakładkę '{section_name}'.")
        tab.click()
        
        # Po kliknięciu czekamy na loader (najpierw na pojawienie się, potem na ukrycie)
        logging.info("Czekam na pojawienie się loadera.")
        page.wait_for_selector("div.loader", state="visible", timeout=60000)
        logging.info("Czekam na ukrycie loadera.")
        page.wait_for_selector("div.loader", state="hidden", timeout=60000)
        
        container_selector = "section.user-page__shelflist"
        current_page = 1
        while True:
            logging.info(f"Przetwarzam stronę {section_name}: {current_page}")
            ebook_item_selector = f"{container_selector} .shelflist-item"
            # Pobieramy elementy bez oczekiwania
            items = page.query_selector_all(ebook_item_selector)
            if not items:
                logging.info(f"Brak elementów {section_name} na stronie {current_page} – lista jest pusta.")
                break
            
            logging.info(f"Znaleziono {len(items)} pozycji na stronie {current_page}.")
            
            for item in items:
                try:
                    title_element = item.query_selector("h3.shelflist-item__title")
                    author_element = item.query_selector("p.shelflist-item__author")
                    img_element = item.query_selector("img.v-lazy-image")
                    
                    title = title_element.inner_text().strip() if title_element else ""
                    author = author_element.inner_text().strip() if author_element else ""
                    cover = img_element.get_attribute("src") if img_element else ""

                    items_found.append({
                        "author": author,
                        "title": title,
                        "cover": cover,
                    })
                except Exception as e:
                    logging.error(f"Błąd podczas przetwarzania elementu {section_name}: {e}")
            
            # Sprawdzamy, czy istnieje przycisk ">" (next)
            next_button_selector = "section.user-page__pagination li.user-page__pagination_dot--next"
            next_button = page.query_selector(next_button_selector)
            if next_button:
                logging.info("Klikam w przycisk '>' (next).")
                next_button.click()
                # Czekamy na loader: najpierw na pojawienie się, potem na jego ukrycie
                logging.info("Czekam na pojawienie się loadera po kliknięciu '>'.")
                page.wait_for_selector("div.loader", state="visible", timeout=20000)
                logging.info("Czekam na ukrycie loadera po kliknięciu '>'.")
                page.wait_for_selector("div.loader", state="hidden", timeout=20000)
                current_page += 1
            else:
                logging.info(f"Brak przycisku '>' – ostatnia strona {section_name}.")
                break
    except Exception as e:
        logging.error(f"Błąd przy przetwarzaniu sekcji {section_name}: {e}")
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
        
    # Po przejściu czekamy na loader (najpierw na pojawienie się, potem na ukrycie)
    logging.info("Czekam na pojawienie się loadera.")
    page.wait_for_selector("div.loader", state="visible", timeout=60000)
    logging.info("Czekam na ukrycie loadera.")
    page.wait_for_selector("div.loader", state="hidden", timeout=60000)


def accept_regulations(page):
    logging.info("Czekam na popup z regulaminem.")
    
    try:
        # Próbujemy wyszukać popup z regulaminem przez krótki czas (np. 10 sekund)
        popup = page.wait_for_selector("#nw_popup_regulations", timeout=10000)
        if popup:
            logging.info("Popup z regulaminem znaleziony, akceptuję regulamin.")
            # Klikamy checkbox – wystarczy kliknąć w element input lub w powiązany span
            page.click("#nw_popup_regulations_checkbox + span.checkmark")
            # Klikamy przycisk "Dalej"
            page.click("#nw_popup_regulations_button")
            # Opcjonalnie: czekamy, aż popup zniknie
            page.wait_for_selector("#nw_popup_regulations", state="detached", timeout=10000)
    except Exception as e:
        # Jeśli popup się nie pojawił lub cokolwiek poszło nie tak, kontynuujemy
        logging.info("Popup z regulaminem nie został znaleziony lub już został obsłużony.")


def process_login(email, password, output_dir, headless=False, log_enabled=False):
    ebook_items = []
    audiobook_items = []

    if not log_enabled:
        logging.disable(logging.CRITICAL)
    else:
        logging.disable(logging.NOTSET)

    with sync_playwright() as playwright:
        try:
            logging.info("Uruchamiam przeglądarkę...")
            # Jeśli headless==False to tryb widoczny
            browser = playwright.chromium.launch(channel="chrome", headless=headless)
            context = browser.new_context()
            page = context.new_page()

            logging.info("Próba logowania...")
            login(page, email, password)

            # Obsługa popupu z regulaminem
            accept_regulations(page)

            # Przejście do dashboardu
            logging.info("Przechodzę do dashboardu użytkownika...")
            page.goto("https://woblink.com/account/dashboard", wait_until="domcontentloaded")

            # Sprawdzenie liczby zakupionych produktów
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
                ebook_items = process_section(page, "EBooki")
                logging.info(f"Znaleziono {len(ebook_items)} pozycji w sekcji 'EBooki'.")

                logging.info("Przetwarzam sekcję 'Audiobooki'.")
                audiobook_items = process_section(page, "Audiobooki")
                logging.info(f"Znaleziono {len(audiobook_items)} pozycji w sekcji 'Audiobooki'.")
            
        except Exception as e:
            logging.exception(f"Napotkano nieoczekiwany błąd: {e}")
        finally:
            logging.info("Zamykam przeglądarkę.")
            browser.close()
    
    # Przygotowywanie podsumowania oraz zapisywanie wyników do pliku
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

    # Zapisz wynik do pliku osobnego dla każdego loginu
    safe_login = sanitize_login_for_filename(email)
    output_filename = f"shelf_{safe_login}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)
    
    print(f"Zapisano wynik do {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Logowanie do woblink")
    parser.add_argument("--login", help="Dane logowania w formacie email:password (np. user@example.com:password123)", required=False)
    parser.add_argument("--credentials-file", help="Ścieżka do pliku z listą danych logowania (login:haslo po jednym w wierszu)", required=False)
    parser.add_argument("--log", help="Włącz logowanie", action="store_true")
    # Flaga --head uruchamia przeglądarkę w trybie widocznym (headful)
    parser.add_argument("--head", help="Uruchom przeglądarkę w trybie widocznym", action="store_true")
    parser.add_argument("--output", help="Katalog docelowy na pliki json (jeśli nie podano, zapisz w 'results_json')", required=False)
    args = parser.parse_args()

    # NIE pozwalaj na brak obu flag login/credentials-file
    if (not args.login and not args.credentials_file) or (args.login and args.credentials_file):
        print("Podaj JEDNĄ flagę: --login email:haslo ALBO --credentials-file plik.txt")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path("results_json")

    headless = not args.head
    log_enabled = args.log

    if args.login:
        try:
            email, password = args.login.split(":", 1)
        except ValueError:
            print("Nieprawidłowy format --login. Oczekiwany: email:haslo")
            sys.exit(1)
        process_login(email, password, output_dir, headless=headless, log_enabled=log_enabled)
    else:
        # credentials-file
        if not os.path.exists(args.credentials_file):
            print(f"Plik {args.credentials_file} nie istnieje.")
            sys.exit(1)
        with open(args.credentials_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                email, password = line.split(":", 1)
                process_login(email.strip(), password.strip(), output_dir, headless=headless, log_enabled=log_enabled)

if __name__ == "__main__":
    main()
