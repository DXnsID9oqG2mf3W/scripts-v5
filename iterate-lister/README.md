# Iterate Lister

Iterate Lister to narzędzie umożliwiające automatyczne uruchamianie skryptu `*-lister.py` dla każdej pary login:hasło zapisanej w pliku tekstowym. Skrypt iteracyjnie przetwarza konta, zapisując wyniki działania dla każdego konta w osobnym pliku.

## Wymagania

- Python 3.7+
- Biblioteki standardowe: argparse, subprocess, os, logging, datetime

## Instalacja

1. Skopiuj plik `iterate-lister.py` do wybranego katalogu.
2. Upewnij się, że masz zainstalowaną odpowiednią wersję Pythona.
3. (Opcjonalnie) Utwórz i aktywuj wirtualne środowisko:
python -m venv venv source venv/bin/activate # Linux/macOS venv\Scripts\activate # Windows

## Użycie

Uruchom skrypt, podając następujące argumenty:

- `--file` - Ścieżka do pliku tekstowego z danymi logowania (każda linia w formacie `login:hasło`).
- `--script` - Ścieżka do skryptu np: `helion-lister.py`.
- `--output` - Ścieżka do katalogu, w którym zapisywane będą wyniki przetwarzania poszczególnych kont.

Przykład użycia:

```bash
python iterate-lister.py --file loginy.txt --script helion-lister.py --output wyniki
```

## Działanie

1. Skrypt sprawdza istnienie pliku z danymi logowania oraz tworzy katalog wyjściowy, jeśli ten nie istnieje.
2. Wczytuje i filtruje dane logowania, uwzględniając tylko linie zawierające dwukropek (:).
3. Dla każdej poprawnej pary login:hasło:
    1. Sprawdza, czy wynik przetwarzania danego konta nie został już wygenerowany.
    2. Uruchamia skrypt *-lister.py z odpowiednimi danymi logowania.
    3. Zapisuje wynik działania skryptu do pliku w podanym katalogu.
4. Działania są logowane z wykorzystaniem kolorowego formatera logów – informacje wyświetlane są zarówno w konsoli, jak i zapisywane do pliku iterate-lister.log.