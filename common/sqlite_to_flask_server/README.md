# sqlite_to_flask_server.py

Panel webowy (Flask) do przeglądania i wyszukiwania danych z bazy SQLite wygenerowanej przez `json_to_sqlite.py`.  
Obsługuje paginację, lazy loading okładek, kopiowanie loginów oraz sortowanie.

## Wymagania

- Python 3.7+
- Flask
- requests

## Instalacja

```sh
pip install flask requests
```

## Użycie

```sh
python sqlite_to_flask_server.py --db results_sqlite/baza.db
```

- `--db`, `-d` – ścieżka do pliku bazy SQLite
- `--host` – adres serwera (domyślnie: 127.0.0.1)
- `--port` – port serwera (domyślnie: 5000)

Przykład:
```sh
python sqlite_to_flask_server.py --db results_sqlite/baza.db --host 0.0.0.0 --port 8080
```

Serwer po uruchomieniu dostępny pod wybranym adresem, np. http://127.0.0.1:5000/
