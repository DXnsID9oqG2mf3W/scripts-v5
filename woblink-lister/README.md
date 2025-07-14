# Woblink Lister

**Woblink Lister** to narzędzie do pobierania listy ebooków i audiobooków z konta woblink.com. Pobiera okładki, autorów i tytuły oraz zapisuje wszystko do pliku JSON.

## Wymagania

- **Google Chrome** (wymagany przez Playwright)
- **Python 3.7+**
- Pakiety Python z pliku `requirements.txt`:
  - playwright >= 1.50.0  
  - tqdm >= 4.66.2  
  - colorama >= 0.4.6  
  - requests >= 2.28.2  

## Instalacja

1. Zainstaluj wymagane biblioteki:
   ```
   pip install -r requirements.txt
   ```
2. Zainstaluj przeglądarki Playwright:
   ```
   playwright install
   ```

## Użycie

Uruchom program z wybraną opcją logowania:

**Opcja 1:** Dane jako jeden argument:
```
python woblink-lister.py --login user@example.com:haslo
```

**Opcja 2:** Lista loginów w pliku tekstowym (jeden login:haslo na linię):
```
python woblink-lister.py --credentials-file konta.txt
```

**Opcje dodatkowe:**
- `--log` – szczegółowe logi z kolorowaniem
- `--head` – uruchom przeglądarkę w trybie widocznym (domyślnie headless)
- `--output <folder>` – gdzie zapisywać pliki JSON (domyślnie: `results_json`)
- `--fix-covers` – automatycznie popraw niepełne okładki (robi backup pliku przed nadpisaniem)

## Działanie

1. Logowanie na woblink.com.
2. Pobranie listy ebooków i audiobooków (okładka, autor, tytuł).
3. Wynik jest zapisywany w pliku JSON, np. `results_json/shelf_user_example_com.json`.
4. Weryfikacja, czy wszystkie okładki mają poprawny URL.
5. W przypadku niepoprawnych okładek można wymusić naprawę opcją `--fix-covers` (ponowne scrollowanie i pobieranie).

## Przykład struktury pliku JSON

```json
{
  "credentials": {
    "login": "user@example.com",
    "password": "haslo"
  },
  "resources": {
    "ebooks": {
      "count": 3,
      "items": [
        {
          "author": "Autor 1",
          "title": "Tytuł ebooka",
          "cover": "https://cdn.woblink.com/cover1.jpg"
        }
      ]
    },
    "audiobooks": {
      "count": 2,
      "items": [
        {
          "author": "Autor 2",
          "title": "Tytuł audiobooka",
          "cover": "https://cdn.woblink.com/cover2.jpg"
        }
      ]
    },
    "courses": {
      "count": 0,
      "items": []
    }
  }
}
```

## Pliki

- `woblink-lister.py` — główny skrypt
- `requirements.txt` — lista bibliotek
- `README.md` — instrukcja

---

**Autor:**  
Projekt edukacyjny, do użytku własnego.
