# json_to_sqlite.py

Konwertuje kolekcję plików JSON (z ebookami, kursami, audiobookami oraz danymi logowania) na jedną bazę SQLite z logicznymi relacjami.

## Wymagania

- Python 3.7+
- Brak zewnętrznych zależności

## Instalacja

Nie wymaga instalowania dodatkowych pakietów.

## Użycie

```sh
python json_to_sqlite.py --input <folder_z_jsonami> --output <folder_wynikowy>
```

- `--input`, `-i` – folder z plikami JSON (każdy plik zgodny ze schematem Woblink/Helion Lister)
- `--output`, `-o` – folder na bazę SQLite (domyślnie: `results_sqlite`)

Przykład:
```sh
python json_to_sqlite.py --input wyniki_json --output results_sqlite
```

Po wykonaniu powstaje plik `baza.db` z tabelami: site, ebooks, audiobooks, courses.
