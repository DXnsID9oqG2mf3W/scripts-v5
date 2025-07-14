# sort_emails_remo_duplicates.py

Sortuje i usuwa duplikaty z pliku tekstowego (np. lista login:hasło lub email:hasło). Szybki i wydajny nawet dla dużych plików.

## Wymagania

- Python 3.7+
- tqdm

## Instalacja

```sh
pip install tqdm
```

## Użycie

```sh
python sort_emails_remo_duplicates.py -i wejscie.txt -o wyjscie.txt
```

- `-i`, `--input` – plik wejściowy
- `-o`, `--output` – plik wyjściowy (opcjonalny, domyślnie nadpisuje wejściowy i robi .bak)

Przykład:
```sh
python sort_emails_remo_duplicates.py -i emails.txt -o emails_sorted.txt
```
