#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import argparse
import re
import shutil

def create_tables(conn):
    """
    Usuwa (jeśli istnieją) i tworzy tabele:
      - domain_info (id, domain)
      - site (id, login, password)
      - ebooks (id, site_id, author, title, cover)
      - courses (id, site_id, author, title, cover)
      - audiobooks (id, site_id, author, title, cover)
    Klucz obcy site_id w tabelach zasobów powiąże wpisy z danymi logowania.
    """
    cursor = conn.cursor()
    # Usuwamy tabele (kolejność ważna – najpierw zasoby, potem site)
    cursor.execute("DROP TABLE IF EXISTS audiobooks")
    cursor.execute("DROP TABLE IF EXISTS courses")
    cursor.execute("DROP TABLE IF EXISTS ebooks")
    cursor.execute("DROP TABLE IF EXISTS site")
    cursor.execute("DROP TABLE IF EXISTS domain_info")
    
    # Tabela domeny – tylko raz dla całej bazy
    cursor.execute("""
        CREATE TABLE domain_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL
        )
    """)
    
    # Tabela site
    cursor.execute("""
        CREATE TABLE site (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Tabela ebooks z kluczem obcym site_id oraz polem cover
    cursor.execute("""
        CREATE TABLE ebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            title TEXT NOT NULL,
            cover TEXT,
            FOREIGN KEY(site_id) REFERENCES site(id)
        )
    """)
    
    # Tabela courses
    cursor.execute("""
        CREATE TABLE courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            title TEXT NOT NULL,
            cover TEXT,
            FOREIGN KEY(site_id) REFERENCES site(id)
        )
    """)
    
    # Tabela audiobooks
    cursor.execute("""
        CREATE TABLE audiobooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            title TEXT NOT NULL,
            cover TEXT,
            FOREIGN KEY(site_id) REFERENCES site(id)
        )
    """)
    conn.commit()

def save_domain(conn, domain):
    """
    Zapisuje domenę do osobnej tabeli (tylko raz dla całej bazy)
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO domain_info (domain) VALUES (?)", (domain,))
    conn.commit()

def process_json_file(file_path, conn):
    """
    Wczytuje dane z pliku JSON i zapisuje je do bazy SQLite.
    Oczekuje struktury:
    
    {
      "credentials": { "login": "xxx", "password": "xxx" },
      "resources": {
        "ebooks": { "count": N, "items": [ {"author": "xxx", "title": "xxx", "cover": "xxx"}, ... ] },
        "courses": { "count": N, "items": [ {"author": "xxx", "title": "xxx", "cover": "xxx"}, ... ] },
        "audiobooks": { "count": N, "items": [ {"author": "xxx", "title": "xxx", "cover": "xxx"}, ... ] }
      }
    }
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cursor = conn.cursor()
    
    # Dodajemy dane logowania do tabeli site
    credentials = data.get("credentials", {})
    login = credentials.get("login", "")
    password = credentials.get("password", "")
    cursor.execute("INSERT INTO site (login, password) VALUES (?, ?)", (login, password))
    site_id = cursor.lastrowid  # id nowego rekordu, który będzie użyty przy zasobach
    
    resources = data.get("resources", {})
    
    # Dodajemy ebooki
    ebooks = resources.get("ebooks", {})
    for item in ebooks.get("items", []):
        author = item.get("author", "")
        title = item.get("title", "")
        cover = item.get("cover", "")
        cursor.execute(
            "INSERT INTO ebooks (site_id, author, title, cover) VALUES (?, ?, ?, ?)",
            (site_id, author, title, cover)
        )
    
    # Dodajemy kursy
    courses = resources.get("courses", {})
    for item in courses.get("items", []):
        author = item.get("author", "")
        title = item.get("title", "")
        cover = item.get("cover", "")
        cursor.execute(
            "INSERT INTO courses (site_id, author, title, cover) VALUES (?, ?, ?, ?)",
            (site_id, author, title, cover)
        )
    
    # Dodajemy audiobooki
    audiobooks = resources.get("audiobooks", {})
    for item in audiobooks.get("items", []):
        author = item.get("author", "")
        title = item.get("title", "")
        cover = item.get("cover", "")
        cursor.execute(
            "INSERT INTO audiobooks (site_id, author, title, cover) VALUES (?, ?, ?, ?)",
            (site_id, author, title, cover)
        )
    
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description="Zamienia kolekcję plików JSON (z informacją o ebookach, kursach, audiobookach) na bazę SQLite.")
    parser.add_argument('--input', '-i', required=True, help='Folder wejściowy z plikami JSON')
    parser.add_argument('--output', '-o', default='results_sqlite', help='Folder wyjściowy na plik bazy SQLite (domyślnie: results_sqlite)')
    parser.add_argument('--domain', '-d', required=True, help='Domena (np. https://helion.pl) – zapisywana raz dla całej bazy')
    args = parser.parse_args()

    input_folder = args.input
    output_folder = args.output
    domain = args.domain

    # Walidacja domeny już na początku
    if not isinstance(domain, str) or not re.match(r"^https?://[a-zA-Z0-9\-\.]+", domain):
        print(f"Błąd: Niepoprawna domena podana w argumencie --domain (\"{domain}\")")
        sys.exit(1)

    if not os.path.isdir(input_folder):
        print("Podana ścieżka do folderu z plikami JSON nie istnieje lub nie jest folderem.")
        sys.exit(1)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Ustalamy ścieżkę do pliku bazy SQLite (np. "baza.db" w folderze wyjściowym)
    db_path = os.path.join(output_folder, "baza.db")
    # BACKUP jeśli istnieje stara baza
    if os.path.isfile(db_path):
        shutil.copy2(db_path, db_path + '.bak')
        print(f"Utworzono kopię zapasową: {db_path}.bak")

    conn = sqlite3.connect(db_path)
    
    # Tworzymy (lub nadpisujemy) tabele z relacjami
    create_tables(conn)

    # Zapisujemy domenę tylko raz dla całej bazy (nowa tabela)
    save_domain(conn, domain)
    
    # Przetwarzamy wszystkie pliki .json w folderze wejściowym
    json_count = 0
    for file in os.listdir(input_folder):
        if file.endswith(".json"):
            file_path = os.path.join(input_folder, file)
            print(f"Przetwarzam plik: {file_path}")
            process_json_file(file_path, conn)
            json_count += 1
    
    conn.close()
    print(f"Baza SQLite utworzona: {db_path}")
    print(f"Zaimportowano plików JSON: {json_count}")

if __name__ == '__main__':
    main()
