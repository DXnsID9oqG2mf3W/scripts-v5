# Woblink Lister

Woblink Lister to narzędzie do wyświetlania listy zasobów (ebooki i audiobooki) konta na woblink.com.

## Wymagania

- Google Chrome
- Python 3.7+
- Biblioteki: playwright, tqdm, colorama, requests
- Konfiguracja Playwright: playwright install

## Instalacja

1. Zainstaluj wymagane pakiety:
   ```
   pip install -r requirements.txt
   ```
2. Zainstaluj przeglądarki Playwright:
   ```
   playwright install
   ```

## Użycie

Uruchom program, podając dane logowania:

**Opcja 1:** Przekazując dane w formacie email:hasło:
```
python woblink-lister.py --login user@example.com:haslo
```

**Opcja 2:** Przekazując dane oddzielnie:
```
python woblink-lister.py --email user@example.com --password haslo
```

Jeśli dane nie zostaną podane, program poprosi o ich interaktywne wprowadzenie.

## Działanie

1. Logowanie na woblink.com.
2. Pobranie informacji o zasobach konta.
3. Zapisanie wyników do pliku tekstowego.
```