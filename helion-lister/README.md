# Helion Lister

**Helion Lister** to narzędzie do pobierania i wyświetlania listy zasobów (ebooki, audiobooki, kursy) przypisanych do konta na helion.pl.

## Wymagania

- **Google Chrome** (wymagany przez Playwright)
- **Python 3.7+**
- Zainstalowane pakiety Python (patrz: `requirements.txt`):

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

Skrypt możesz uruchomić na kilka sposobów:

**1. Przekazując dane logowania jako jeden argument:**
```
python helion-lister.py --login user@example.com:haslo
```

**2. Osobno podając email i hasło:**
```
python helion-lister.py --email user@example.com --password haslo
```

**3. Bez parametrów – program poprosi o dane interaktywnie.**

**Opcjonalnie:**  
Dodaj `--log` by zobaczyć szczegółowe logi z kolorowaniem:
```
python helion-lister.py --login user@example.com:haslo --log
```

## Działanie

1. Loguje się na helion.pl na podane konto.
2. Pobiera informację o liczbie ebooków, audiobooków, kursów.
3. Wyświetla szczegółową listę wszystkich zasobów (autor + tytuł) w konsoli, oddzielnie dla każdego typu.
4. Wynik jest sortowany według autora (alfabetycznie).

## Informacje dodatkowe

- W przypadku braku zasobów w danej kategorii, kategoria nie pojawia się na liście wynikowej.
- Skrypt korzysta z Playwright i Chrome, więc Chrome musi być zainstalowany lokalnie.
- Obsługiwane są sytuacje nietypowe – np. błędne logowanie, brak dostępu do zasobów lub błędy połączenia.
- Szczegółowe logi dostępne są po dodaniu opcji `--log`.

## Przykład wyjścia

```
Ebooki:
Autor 1 - Tytuł 1
Autor 2 - Tytuł 2

Audiobooki:
Autor 3 - Tytuł 3

Kursy:
Autor 4 - Tytuł 4
```

## Pliki

- `helion-lister.py` — główny skrypt
- `requirements.txt` — lista wymaganych bibliotek

---

**Autor:**  
Projekt na własny użytek edukacyjny.  
