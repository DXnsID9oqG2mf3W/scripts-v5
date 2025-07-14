#!/usr/bin/env python3
import os
import sys
import sqlite3
import argparse
import hashlib
import requests
from flask import Flask, render_template_string, request, send_from_directory, abort
from collections import defaultdict

# ANSI colors for logs
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"

def log_book(action, category, title, author, url, msg, color=Color.RESET):
    prefix = f"{Color.BOLD}{color}[{action}]{Color.RESET}"
    meta = f"{Color.CYAN}{category}{Color.RESET} | {Color.YELLOW}{title}{Color.RESET} | {Color.GREEN}{author}{Color.RESET}"
    urlinfo = f"{Color.GRAY}{url or '-'}{Color.RESET}"
    print(f"{prefix} {meta}\n      {urlinfo}\n    {msg}{Color.RESET}")

BOOTSTRAP = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {
    padding-top: 72px;
    background: #f8f9fa;
}
.sticky-top {
    z-index: 1020 !important;
}
.navbar {
    box-shadow: 0 2px 10px #0001;
    background: #fffefe;
}
#covers-progress {
    position: fixed;
    top: 20px;
    right: 20px;
    min-width: 160px;
    z-index: 9999;
    background: #212529ee;
    color: #fff;
    padding: 0.75em 1.25em;
    border-radius: 12px;
    font-weight: 600;
    font-size: 1rem;
    display: none;
}
.card-img-top, .placeholder-cover {
    width: 100%;
    height: 240px;
    object-fit: contain;
    background: #ececec;
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 60px;
    transition: filter 0.25s cubic-bezier(.4,2,.6,1);
}
.cover-hover {
    position: relative;
    overflow: visible;
}
.cover-mask {
    transition: opacity 0.25s;
    opacity: 0;
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(24,29,49,0.62);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2;
    pointer-events: none;
}
.cover-hover:hover .cover-mask {
    opacity: 1;
    pointer-events: all;
}
.cover-mask .btn-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: center;
}
.cover-mask .btn {
    min-width: 180px;
    font-size: 1em;
    box-shadow: 0 1px 8px #0002;
    font-weight: 600;
}
.page-link.active, .page-link:active {
    background: #0056b3 !important;
    color: #fff !important;
}
.page-item.disabled .page-link {
    pointer-events: none;
    opacity: 0.45;
}
</style>
"""

LAZY_JS = """
<script>
function makeBookSvg() {
    return `<svg width="64" height="64" fill="currentColor" viewBox="0 0 24 24">
      <path d="M5 19V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v13"/>
      <path d="M5 19a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2"/>
      <line x1="5" y1="19" x2="19" y2="19"/>
    </svg>`;
}
function loadCover(div, url) {
    fetch(url)
        .then(resp => {
            if (!resp.ok) throw "not found";
            return resp.blob();
        })
        .then(blob => {
            const img = document.createElement('img');
            img.className = 'card-img-top';
            img.style = "height:240px;object-fit:contain;";
            img.src = URL.createObjectURL(blob);
            div.parentNode.replaceChild(img, div);
        })
        .catch(_ => { /* stays as placeholder */ });
}
document.addEventListener('DOMContentLoaded', function() {
    const placeholders = document.querySelectorAll('.placeholder-cover[data-cover-id]');
    let left = placeholders.length;
    let shown = false;
    const progress = document.getElementById('covers-progress');
    function update() {
        if (left > 0) {
            progress.style.display = 'block';
            progress.textContent = "Pobieranie okładek: " + left;
            shown = true;
        } else if (shown) {
            progress.style.display = 'none';
        }
    }
    update();
    // LAZY loading using IntersectionObserver
    if ('IntersectionObserver' in window) {
        let observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if(entry.isIntersecting) {
                    const div = entry.target;
                    const url = div.dataset.coverId;
                    loadCover(div, url);
                    obs.unobserve(div);
                    left -= 1;
                    update();
                }
            });
        }, {rootMargin:"250px"});
        placeholders.forEach(div => observer.observe(div));
    } else {
        // fallback: load all (old browsers)
        placeholders.forEach(div => {
            loadCover(div, div.dataset.coverId);
            left -= 1;
            update();
        });
    }
    // BUTTON HANDLERS
    document.body.addEventListener('click', function(e) {
        if(e.target.dataset && e.target.dataset.google) {
            let title = e.target.dataset.title || '';
            let q = encodeURIComponent(`${title} woblink.com`);
            window.open('https://woblink.com/katalog/ksiazki?szukasz=' + q, '_blank');
        }
        if(e.target.dataset && e.target.dataset.copylogin) {
            let loginpass = e.target.dataset.copylogin;
            if (navigator.clipboard) {
                navigator.clipboard.writeText(loginpass).then(function() {
                    e.target.innerText = "Skopiowano!";
                    setTimeout(() => { e.target.innerText = "Kopiuj dane logowania"; }, 1400);
                });
            }
        }
        if(e.target.dataset && e.target.dataset.copyloginOpen) {
            let loginpass = e.target.dataset.copyloginOpen;
            if (navigator.clipboard) {
                navigator.clipboard.writeText(loginpass).then(function() {
                    window.open('https://woblink.com/logowanie', '_blank');
                });
            }
        }
    });
});
</script>
"""

TEMPLATE = BOOTSTRAP + """
<nav class="navbar navbar-expand-lg navbar-light bg-light sticky-top">
  <div class="container">
    <a class="navbar-brand" href="#">Panel Biblioteka</a>
    <div class="d-flex ms-auto">
      <span class="navbar-text text-muted me-3" style="font-size:1em;">{{total_items}} wyników</span>
    </div>
  </div>
</nav>
<div id="covers-progress"></div>
<div class="container mt-2 mb-5">
  <form method="get" class="row g-3 mb-3 align-items-center">
    <div class="col-auto">
      <select class="form-select" name="category">
        {% for cat in ['ebooks', 'audiobooks', 'courses'] %}
          <option value="{{cat}}" {% if cat==category %}selected{% endif %}>{{cat}}</option>
        {% endfor %}
      </select>
    </div>
    <div class="col-auto">
      <select class="form-select" name="sort">
        <option value="author" {% if sort=='author' %}selected{% endif %}>Autor (A-Z)</option>
        <option value="title" {% if sort=='title' %}selected{% endif %}>Tytuł (A-Z)</option>
      </select>
    </div>
    <div class="col-auto">
      <select class="form-select" name="per_page">
        {% for n in [25, 50, 100, 200] %}
        <option value="{{n}}" {% if n==per_page %}selected{% endif %}>{{n}} na stronę</option>
        {% endfor %}
      </select>
    </div>
    <div class="col-auto">
      <button class="btn btn-primary">Wyświetl</button>
    </div>
    <div class="col text-end text-muted" style="font-size:0.95em;">
      Strona <b>{{page}}</b> z <b>{{pages|length>0 and pages[-1] or 1}}</b>
    </div>
  </form>
  <!-- TOP PAGINATOR -->
  <nav aria-label="Paginacja" class="mb-3">
    <ul class="pagination justify-content-center">
      <li class="page-item {% if page==1 %}disabled{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page=1">&laquo;</a>
      </li>
      {% for p in pages %}
      <li class="page-item {% if p==page %}active{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page={{p}}">{{p}}</a>
      </li>
      {% endfor %}
      <li class="page-item {% if page==pages|last %}disabled{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page={{pages|last}}">&raquo;</a>
      </li>
    </ul>
  </nav>
  <div class="row">
    {% for item in items %}
    <div class="col-md-4 col-sm-6 mb-4">
      <div class="card h-100 shadow-sm cover-hover" style="overflow:visible; position:relative;">
        <div class="placeholder-cover"
            {% if item.cover_url %}data-cover-id="{{item.cover_url}}"{% endif %}>
            <svg width="64" height="64" fill="currentColor" viewBox="0 0 24 24">
              <path d="M5 19V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v13"/>
              <path d="M5 19a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2"/>
              <line x1="5" y1="19" x2="19" y2="19"/>
            </svg>
        </div>
        <div class="cover-mask">
            <div class="btn-group">
                <button type="button" class="btn btn-primary"
                    data-google="1"
                    data-title="{{item.title}}">
                    Szukaj w Woblink
                </button>
                {% if item.login_pass_list_idx %}
                    {% for idx, lp in item.login_pass_list_idx %}
                        <button type="button" class="btn btn-secondary mb-1"
                            data-copylogin="{{lp}}">
                            Kopiuj dane logowania #{{idx}}
                        </button>
                    {% endfor %}
                {% endif %}
            </div>
        </div>
        <div class="card-body">
          <h5 class="card-title">{{item.title}}</h5>
          <p class="card-text"><b>Autor:</b> {{item.author}}</p>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  <!-- BOTTOM PAGINATOR -->
  <nav aria-label="Paginacja" class="mt-3">
    <ul class="pagination justify-content-center">
      <li class="page-item {% if page==1 %}disabled{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page=1">&laquo;</a>
      </li>
      {% for p in pages %}
      <li class="page-item {% if p==page %}active{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page={{p}}">{{p}}</a>
      </li>
      {% endfor %}
      <li class="page-item {% if page==pages|last %}disabled{% endif %}">
        <a class="page-link" href="?category={{category}}&sort={{sort}}&per_page={{per_page}}&page={{pages|last}}">&raquo;</a>
      </li>
    </ul>
  </nav>
</div>
""" + LAZY_JS

def hash_url(url):
    return hashlib.sha256((url or "").encode('utf-8')).hexdigest()

def ensure_cache_dir():
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqlite_to_flask_server_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_cover_local_path(url):
    cache_dir = ensure_cache_dir()
    ext = os.path.splitext((url or "").split("?")[0])[1] if url else ".svg"
    filename = hash_url(url) + (ext if ext else ".img")
    return os.path.join(cache_dir, filename)

def write_placeholder(local_path):
    svg = b'''<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 64 64">
      <rect width="100%" height="100%" fill="#ececec"/>
      <path d="M12 56V12a4 4 0 0 1 4-4h32a4 4 0 0 1 4 4v44" fill="none" stroke="#b5b5b5" stroke-width="3"/>
      <path d="M12 56a4 4 0 0 0 4 4h32a4 4 0 0 0 4-4" fill="none" stroke="#b5b5b5" stroke-width="3"/>
      <line x1="12" y1="56" x2="52" y2="56" stroke="#b5b5b5" stroke-width="3"/>
    </svg>'''
    with open(local_path, "wb") as f:
        f.write(svg)

def create_app(db_path):
    app = Flask(__name__)
    cache_dir = ensure_cache_dir()

    def get_total_items(category):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {category}")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def get_items(category='ebooks', sort=None, per_page=50, page=1):
        if category not in ['ebooks', 'audiobooks', 'courses']:
            category = 'ebooks'
        sort_clause = "author COLLATE NOCASE ASC, title COLLATE NOCASE ASC"
        if sort == "title":
            sort_clause = "title COLLATE NOCASE ASC"
        elif sort == "author":
            sort_clause = "author COLLATE NOCASE ASC, title COLLATE NOCASE ASC"
        per_page = max(1, min(200, int(per_page)))
        page = max(1, int(page))
        offset = (page-1)*per_page
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT {category}.author, {category}.title, {category}.cover, site.login, site.password
            FROM {category} JOIN site ON {category}.site_id = site.id
            ORDER BY {sort_clause}
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        rows = cursor.fetchall()
        conn.close()
        grouped = defaultdict(lambda: {"author": "", "title": "", "cover_url": None, "login_pass_list": []})
        for r in rows:
            key = (r[0], r[1])
            cover_remote = r[2] if r[2] else None
            cover_url = f"/cover/{hash_url(cover_remote)}" if cover_remote else None
            login_pass = f"{r[3]}:{r[4]}" if r[3] and r[4] else None
            grouped[key]["author"] = r[0]
            grouped[key]["title"] = r[1]
            grouped[key]["cover_url"] = cover_url
            if login_pass:
                grouped[key]["login_pass_list"].append(login_pass)
        items = list(grouped.values())
        # Dodajemy numerację do login_pass_list dla Jinja2
        for item in items:
            item["login_pass_list_idx"] = list(enumerate(item["login_pass_list"], start=1))
        return items

    @app.route("/")
    def index():
        category = request.args.get("category", "ebooks")
        sort = request.args.get("sort", None)
        try:
            per_page = int(request.args.get("per_page", 50))
        except Exception:
            per_page = 50
        try:
            page = int(request.args.get("page", 1))
        except Exception:
            page = 1
        per_page = per_page if per_page in [25, 50, 100, 200] else 50
        total_items = get_total_items(category)
        last_page = max(1, (total_items + per_page - 1) // per_page)
        page = min(max(1, page), last_page)
        if last_page <= 7:
            pages = list(range(1, last_page+1))
        else:
            if page <= 4:
                pages = list(range(1, 8))
            elif page > last_page-4:
                pages = list(range(last_page-6, last_page+1))
            else:
                pages = list(range(page-3, page+4))
        items = get_items(category, sort, per_page, page)
        return render_template_string(
            TEMPLATE,
            items=items,
            category=category,
            sort=sort or "author",
            page=page,
            per_page=per_page,
            total_items=total_items,
            pages=pages
        )

    @app.route("/cover/<cover_id>")
    def cover(cover_id):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        found_url = None
        title = author = category = None
        for cat in ['ebooks', 'audiobooks', 'courses']:
            cursor.execute(f"SELECT title, author, cover FROM {cat} WHERE cover IS NOT NULL")
            for row in cursor.fetchall():
                t, a, url = row
                if hash_url(url) == cover_id:
                    found_url = url
                    title = t
                    author = a
                    category = cat
                    break
            if found_url:
                break
        conn.close()
        local_path = get_cover_local_path(found_url if found_url else cover_id)
        log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Przetwarzanie okładki", Color.BLUE)
        if os.path.exists(local_path):
            log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Z cache: {local_path}", Color.GREEN)
            return send_from_directory(os.path.dirname(local_path), os.path.basename(local_path))
        if (not found_url) or found_url.strip().startswith("/") or not found_url.lower().startswith(("http://", "https://")):
            log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Adres brak lub względny, zapisuję placeholder", Color.YELLOW)
            write_placeholder(local_path)
            return send_from_directory(os.path.dirname(local_path), os.path.basename(local_path))
        try:
            log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Pobieram z internetu", Color.CYAN)
            r = requests.get(found_url, timeout=10)
            if r.status_code == 200 and r.content:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Pobrano i zapisano: {local_path}", Color.GREEN)
            else:
                log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Błąd pobierania ({r.status_code}), zapisuję placeholder", Color.RED)
                write_placeholder(local_path)
        except Exception as e:
            log_book("COVER", category or "-", title or "-", author or "-", found_url, f"Błąd pobierania ({e}), zapisuję placeholder", Color.RED)
            write_placeholder(local_path)
        return send_from_directory(os.path.dirname(local_path), os.path.basename(local_path))

    return app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Panel administracyjny z paginacją, lazy loadingiem i przyciskiem kopiowania loginu.")
    parser.add_argument("--db", "-d", help="Ścieżka do bazy SQLite", default="results_sqlite/baza.db")
    parser.add_argument("--host", default="127.0.0.1", help="Adres serwera (domyślnie: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port serwera (domyślnie: 5000)")
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print(f"Błąd: Plik bazy nie istnieje: {args.db}")
        print("Utwórz bazę za pomocą skryptu importującego przed uruchomieniem panelu.")
        sys.exit(1)

    app = create_app(args.db)
    print(f"Serwer działa na http://{args.host}:{args.port}/ (baza: {args.db})")
    app.run(host=args.host, port=args.port, debug=False)
