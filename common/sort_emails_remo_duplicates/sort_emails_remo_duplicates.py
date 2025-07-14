import sqlite3
import argparse
import os
from tqdm import tqdm
import shutil

def main():
    parser = argparse.ArgumentParser(description="Usuń duplikaty i posortuj plik.")
    parser.add_argument("-i", "--input", required=True, help="Plik wejściowy")
    parser.add_argument("-o", "--output", help="Plik wyjściowy (opcjonalnie)")
    args = parser.parse_args()
    input_file = args.input

    if args.output:
        output_file = args.output
        backup_needed = False
    else:
        output_file = input_file
        backup_needed = True

    # Backup jeśli nadpisujemy oryginał
    if backup_needed:
        backup_file = f"{input_file}.bak"
        shutil.copy2(input_file, backup_file)
        print(f"Stworzono kopię oryginału: {backup_file}")

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE creds (line TEXT UNIQUE)")

    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"Liczba linii w pliku: {len(lines)}")

    for line in tqdm(lines, desc="Przetwarzanie linii"):
        line = line.strip()
        if line:
            cur.execute("INSERT OR IGNORE INTO creds VALUES (?)", (line,))

    print("Sortowanie i zapis...")

    cur.execute("SELECT line FROM creds ORDER BY line")
    rows = cur.fetchall()

    with open(output_file, "w", encoding="utf-8") as f:
        for (line,) in tqdm(rows, desc="Zapisywanie do pliku"):
            f.write(f"{line}\n")

    print(f"Gotowe. Wynik zapisano w pliku: {output_file}")
    print(f"Liczba unikalnych linii: {len(rows)}")

    conn.close()

if __name__ == "__main__":
    main()
