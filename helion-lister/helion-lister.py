import os
import re
import requests
import base64
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import argparse
from pathlib import Path
import getpass
import sys
import io
import time
import logging
from colorama import init, Fore, Style

# Initialization of colorama (ensures color reset)
init(autoreset=True)

# Definition of custom "SUCCESS" level
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)

# Adding the success method to the Logger class
logging.Logger.success = success
logging.success = logging.getLogger().success

# Definition of a custom colored formatter
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

# Configuring logger with colored formatting
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.DEBUG, handlers=[handler])

# Setting proper console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)


def list_items(page, url, category):
    logging.info(f"Listing {category} from: {url}")
    try:
        page.goto(url, wait_until='domcontentloaded')
    except Exception as e:
        logging.error(f"Failed to navigate to {url}: {e}")
        return []

    url_with_100_items = f"{url}?onPage=100"
    try:
        page.goto(url_with_100_items, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
    except Exception as e:
        logging.error(f"Error loading page with 100 items ({url_with_100_items}): {e}")
        return []

    all_titles = []
    try:
        current_url = page.url
        all_links = page.query_selector_all('a[href^="/users/konto/biblioteka/"]')
        page_numbers = []
        for link in all_links:
            href = link.get_attribute('href')
            match = re.search(r'page=(\d+)', href)
            if match:
                page_numbers.append(int(match.group(1)))
        if not page_numbers:
            page_numbers = [1]
        max_page_number = max(page_numbers)
        logging.info(f"Total pages for {category}: {max_page_number}")
    except Exception as e:
        logging.error(f"Error parsing pagination on page {url}: {e}")
        return []

    for page_num in range(1, max_page_number + 1):
        try:
            page_url = f"{current_url}&page={page_num}"
            logging.info(f"Processing {category} - Page {page_num} ({page_url})")
            page.goto(page_url, wait_until='domcontentloaded')
            items = page.query_selector_all('ul#listBooks li')
            if not items:
                logging.warning(f"No items found on page {page_num} for category {category}")
            for item in items:
                try:
                    title_element = item.query_selector('h3.title')
                    author_element = item.query_selector('p.author')
                    if title_element and author_element:
                        title = title_element.inner_text().strip()
                        author = author_element.inner_text().strip()
                        all_titles.append((author, title))
                    else:
                        logging.warning(f"Missing title or author in an item on page {page_num}")
                except Exception as e:
                    logging.error(f"Error processing item on page {page_num} for category {category}: {e}")
        except Exception as e:
            logging.error(f"Failed to process page {page_num} for category {category}: {e}")

    all_titles.sort(key=lambda x: x[0].lower())
    logging.info(f"Found {len(all_titles)} items in category {category}.")

    # Logging every element we found
    for author, title in all_titles:
        logging.debug(f"{author} - {title}")

    return all_titles


def login(page, email, password):
    login_url = 'https://helion.pl/users/login'
    logging.info(f"Navigating to login page: {login_url}")
    try:
        page.goto(login_url, wait_until='domcontentloaded')
    except Exception as e:
        logging.error(f"Failed to load login page {login_url}: {e}")
        raise

    try:
        if page.is_visible('button#CybotCookiebotDialogBodyButtonDecline'):
            page.click('button#CybotCookiebotDialogBodyButtonDecline')
    except Exception as e:
        logging.warning(f"Cookie decline button not found or could not be clicked: {e}")

    try:
        logging.info("Filling in login credentials.")
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', password)
        page.click('#log_in_submit')
    except Exception as e:
        logging.error(f"Error submitting login form: {e}")
        raise


def get_user_info(page):
    # Ensure we are on a page containing "/users"
    if "/users" not in page.url:
        logging.info(f"Current URL ({page.url}) does not contain '/users'. Navigating to /users page.")
        page.goto("https://helion.pl/users", wait_until="domcontentloaded")

    logging.info("Fetching user information via API.")
    api_url = 'https://helion.pl/api/users/info'

    for attempt in range(1, 31):
        logging.info(f"Attempt {attempt} to fetch user information.")
        try:
            response = page.context.request.get(api_url)
            status_code = response.status
            response_text = response.text()
            logging.debug(f"Response status code: {status_code}")
            logging.debug(f"Response content: {response_text}")

            if status_code == 200:
                json_data = response.json()
                biblioteka = json_data.get("biblioteka")
                if biblioteka is None:
                    logging.error("No library information in the response.")
                # If 'biblioteka' is a list
                elif isinstance(biblioteka, list):
                    if biblioteka == [0, 0, 0, 0]:
                        logging.info("User has no resources yet (all zeros). Retrying...")
                    else:
                        if len(biblioteka) >= 4:
                            converted = {
                                "ebooks": biblioteka[0],
                                "audiobooks": biblioteka[1],
                                "courses": biblioteka[2],
                                "addition": biblioteka[3]
                            }
                            logging.success("User information fetched successfully.")
                            return converted
                        else:
                            logging.error("Invalid library data format.")
                # If 'biblioteka' is a dict
                elif isinstance(biblioteka, dict):
                    if (biblioteka.get("ebooks", 0) != 0 or
                        biblioteka.get("audiobooks", 0) != 0 or
                        biblioteka.get("courses", 0) != 0 or
                        biblioteka.get("addition", 0) != 0):
                        logging.success("User information fetched successfully.")
                        return biblioteka
                    else:
                        logging.info("User has no resources yet (all zeros). Retrying...")
                else:
                    logging.error("Unexpected library data format.")
            else:
                logging.error(f"API error while fetching user information. Status code: {status_code}, response: {response_text}")
        except Exception as e:
            logging.exception(f"Exception while fetching user information (attempt {attempt}): {e}")

        if attempt < 30:
            logging.info("Waiting 1 second before the next attempt...")
            time.sleep(1)

    logging.error("Failed to fetch valid user information after 30 attempts.")
    return {}


def main():
    parser = argparse.ArgumentParser(description="Login to helion")
    parser.add_argument("--login", help="Login credentials in the format email:password (e.g. user@example.com:password123)", required=False)
    parser.add_argument("--email", help="Your email address", required=False)
    parser.add_argument("--password", help="Your password", required=False)
    parser.add_argument("--log", help="Enable logging output", action="store_true")
    args = parser.parse_args()

    # Jeśli nie podano --log, wyłączamy logowanie
    if not args.log:
        logging.disable(logging.CRITICAL)

    # Jeśli --login jest podane, rozdzielamy dane logowania
    if args.login:
        try:
            email, password = args.login.split(":", 1)
        except ValueError:
            logging.error("Invalid login credentials format. Expected format: email:password")
            sys.exit(1)
    else:
        email = args.email or input("Enter email: ")
        password = args.password or getpass.getpass("Enter password: ")

    # Variables to store results
    ebooks_results = []
    audiobooks_results = []
    courses_results = []

    with sync_playwright() as playwright:
        try:
            logging.info("Launching browser...")
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context()
            page = context.new_page()

            logging.info("Attempting to log in...")
            login(page, email, password)

            logging.info("Fetching user information...")
            user_info = get_user_info(page)

            if user_info == [0, 0, 0, 0] or not user_info:
                logging.error("User has no resources.")
                browser.close()
                return

            title_parts = []
            if user_info.get("ebooks", 0) > 0:
                title_parts.append(f"ebooks: {user_info['ebooks']}")
            if user_info.get("audiobooks", 0) > 0:
                title_parts.append(f"audiobooks: {user_info['audiobooks']}")
            if user_info.get("courses", 0) > 0:
                title_parts.append(f"courses: {user_info['courses']}")
            #if user_info.get("addition", 0) > 0:
            #    title_parts.append(f"addons: {user_info['addition']}")

            logging.success("helion.pl - " + ", ".join(title_parts))

            # Retrieve lists if resources are available
            if user_info.get("ebooks", 0) > 0:
                ebooks_url = 'https://helion.pl/users/konto/biblioteka/ebooki'
                logging.info("Fetching Ebooks list.")
                ebooks_results = list_items(page, ebooks_url, "Ebooks")

            if user_info.get("audiobooks", 0) > 0:
                audiobooks_url = 'https://helion.pl/users/konto/biblioteka/audiobooki'
                logging.info("Fetching Audiobooks list.")
                audiobooks_results = list_items(page, audiobooks_url, "Audiobooks")

            if user_info.get("courses", 0) > 0:
                courses_url = 'https://helion.pl/users/konto/biblioteka/kursy'
                logging.info("Fetching Courses list.")
                courses_results = list_items(page, courses_url, "Courses")

        except Exception as e:
            logging.exception(f"Unexpected error encountered: {e}")
        finally:
            logging.info("Closing browser.")
            browser.close()
            
            # Writing out the final result (without logging)
            sections = []

            if ebooks_results:
                ebook_lines = ["Ebooki:"]
                for author, title in ebooks_results:
                    ebook_lines.append(f"{author} - {title}")
                sections.append("\n".join(ebook_lines))

            if audiobooks_results:
                audiobook_lines = ["Audiobooki:"]
                for author, title in audiobooks_results:
                    audiobook_lines.append(f"{author} - {title}")
                sections.append("\n".join(audiobook_lines))

            if courses_results:
                courses_lines = ["Kursy:"]
                for author, title in courses_results:
                    courses_lines.append(f"{author} - {title}")
                sections.append("\n".join(courses_lines))

            # Print the result without unnecessary additional new lines
            print("\n\n".join(sections))


if __name__ == "__main__":
    main()
