import argparse
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, g, make_response, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "awards.db"

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET", "change-me"),
    DATABASE=str(DB_PATH),
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):  # noqa: ANN001
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS nominations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nominees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomination_id INTEGER NOT NULL REFERENCES nominations(id),
            name TEXT NOT NULL,
            description TEXT,
            photo_url TEXT
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomination_id INTEGER NOT NULL REFERENCES nominations(id),
            nominee_id INTEGER NOT NULL REFERENCES nominees(id),
            ip_address TEXT,
            voter_cookie TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


NOMINEE_POOL = [
    "Захар",
    "Артем М.",
    "Маша",
    "Катя",
    "Тимур",
    "Ярик",
    "Артем Х.",
    "Славик",
    "Самбор",
    "Егор",
    "Марк",
    "Денис",
    "Сана",
    "Назар",
    "Арина",
    "Рита",
    "Яра",
    "Андрей",
    "Саня",
    "Леха",
    "Олег",
    "Даша",
]


def build_nominee_entries() -> list[dict[str, str | None]]:
    return [
        {
            "name": name,
            "description": "Своя легенда нашего круга — в этой категории.",
            "photo_url": None,
        }
        for name in NOMINEE_POOL
    ]


DEFAULT_NOMINATIONS = [
    {
        "title": "King года",
        "description": "Человек, который всегда ведет себя так, будто он главный и все это поддерживают.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Queen года",
        "description": "Персона с эффектной подачей,стиль, эмоции, жесты.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Мем года",
        "description": "Источник самых смешных моментов года.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Человек мем года",
        "description": "Главный генератор мемов.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Нон актив года",
        "description": "Тот кого как будто «нету».",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Долбоеб года",
        "description": "Без объяснений",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Харизма года",
        "description": "Человек, который просто появляется — и настроение у всех становится лучше.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Пунктуальность года",
        "description": "Без объяснений.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Токсик года",
        "description": "Мастер колких комментариев и пассивной агрессии. Иногда бесит, но всегда добавляет специй в беседу.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Лентяй года",
        "description": "Тот которому всегда лень.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Актив года",
        "description": "Самый активный участник группы, инициатор.",
        "nominees": build_nominee_entries(),
    },
    {
        "title": "Завоз года",
        "description": "Тот, кто внезапно завёз лучший вайб, идеи, шутки или стиль.",
        "nominees": build_nominee_entries(),
    },
]

def seed_default_data():
    db = get_db()
    existing = db.execute("SELECT COUNT(*) AS total FROM nominations").fetchone()
    nominee_total = db.execute("SELECT COUNT(*) AS total FROM nominees").fetchone()
    expected_total = len(DEFAULT_NOMINATIONS)
    expected_nominees = expected_total * len(NOMINEE_POOL)
    if existing["total"] != expected_total or nominee_total["total"] != expected_nominees:
        db.execute("DELETE FROM votes")
        db.execute("DELETE FROM nominees")
        db.execute("DELETE FROM nominations")

    for nomination in DEFAULT_NOMINATIONS:
        cursor = db.execute(
            "INSERT INTO nominations (title, description) VALUES (?, ?)",
            (nomination["title"], nomination["description"]),
        )
        nomination_id = cursor.lastrowid
        for nominee in nomination["nominees"]:
            db.execute(
                """
                INSERT INTO nominees (nomination_id, name, description, photo_url)
                VALUES (?, ?, ?, ?)
                """,
                (
                    nomination_id,
                    nominee["name"],
                    nominee.get("description"),
                    nominee.get("photo_url"),
                ),
            )
    db.commit()


def fetch_nominations():
    db = get_db()
    nominations = db.execute(
        "SELECT id, title, description FROM nominations ORDER BY id"
    ).fetchall()
    nominees = db.execute(
        "SELECT id, nomination_id, name, description, photo_url FROM nominees"
    ).fetchall()
    nominees_by_nomination: dict[int, list[sqlite3.Row]] = {}
    for nominee in nominees:
        nominees_by_nomination.setdefault(nominee["nomination_id"], []).append(nominee)
    return [
        {
            "id": n["id"],
            "title": n["title"],
            "description": n["description"],
            "nominees": nominees_by_nomination.get(n["id"], []),
        }
        for n in nominations
    ]


@app.route("/")
def index():
    nominations = fetch_nominations()
    return render_template("index.html", nominations=nominations)


@app.route("/nominations")
def nominations_view():
    nominations = fetch_nominations()
    return render_template("nominations.html", nominations=nominations)


def user_has_voted(voter_cookie: str | None, ip_address: str | None) -> bool:
    db = get_db()
    query = "SELECT 1 FROM votes WHERE voter_cookie = ? OR ip_address = ? LIMIT 1"
    return db.execute(query, (voter_cookie, ip_address)).fetchone() is not None


@app.route("/vote", methods=["GET", "POST"])
def vote():
    nominations = fetch_nominations()
    if request.method == "POST":
        voter_cookie = request.cookies.get("voter_id") or uuid.uuid4().hex
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        if user_has_voted(voter_cookie, user_ip):
            response = make_response(redirect(url_for("already_voted")))
            response.set_cookie("voter_id", voter_cookie, max_age=60 * 60 * 24 * 365, samesite="Lax")
            return response

        missing = [n for n in nominations if not request.form.get(f"nomination_{n['id']}")]
        if missing:
            flash("Выберите по одному номинанту в каждой номинации.", "error")
            return render_template("vote.html", nominations=nominations)

        db = get_db()
        now = datetime.utcnow().isoformat()
        for nomination in nominations:
            nominee_id = request.form.get(f"nomination_{nomination['id']}")
            db.execute(
                """
                INSERT INTO votes (nomination_id, nominee_id, ip_address, voter_cookie, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (nomination["id"], nominee_id, user_ip, voter_cookie, now),
            )
        db.commit()

        response = make_response(redirect(url_for("thanks")))
        response.set_cookie("voter_id", voter_cookie, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return response

    return render_template("vote.html", nominations=nominations)


@app.route("/thanks")
def thanks():
    return render_template("thanks.html")


@app.route("/already-voted")
def already_voted():
    return render_template("already_voted.html")


def require_admin():
    expected_token = os.environ.get("ADMIN_TOKEN", "letmein")
    provided = request.args.get("token")
    if expected_token and provided != expected_token:
        abort(403)


@app.route("/admin")
def admin():
    require_admin()
    db = get_db()
    rows = db.execute(
        """
        SELECT n.title AS nomination_title,
               nm.name AS nominee_name,
               COUNT(v.id) AS vote_count
        FROM nominations n
        JOIN nominees nm ON nm.nomination_id = n.id
        LEFT JOIN votes v ON v.nominee_id = nm.id
        GROUP BY n.id, nm.id
        ORDER BY n.id, vote_count DESC
        """
    ).fetchall()
    results: list[dict[str, object]] = []
    current_title: str | None = None
    bucket: list[dict[str, int | str]] = []

    def commit_group(title: str | None, items: list[dict[str, int | str]]):
        if title is None:
            return
        total = sum(int(item["count"]) for item in items)
        for item in items:
            item["percent"] = 0 if total == 0 else round((int(item["count"]) / total) * 100)
        results.append({"title": title, "items": items, "total": total})

    for row in rows:
        if current_title != row["nomination_title"]:
            commit_group(current_title, bucket)
            current_title = row["nomination_title"]
            bucket = []
        bucket.append({"name": row["nominee_name"], "count": row["vote_count"]})

    commit_group(current_title, bucket)
    return render_template("admin.html", results=results)


@app.errorhandler(403)
def forbidden(_):  # noqa: ANN001
    return render_template("403.html"), 403


@app.cli.command("init-db")
def init_db_command():
    """CLI helper: flask init-db"""
    init_db()
    with app.app_context():
        seed_default_data()
    print("База данных создана и заполнена демо-данными.")


def main():
    parser = argparse.ArgumentParser(description="Award voting site")
    parser.add_argument("--init-db", action="store_true", help="Создать таблицы и демо-данные")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    if args.init_db:
        init_db()
        with app.app_context():
            seed_default_data()
        print(f"База создана в {app.config['DATABASE']}")
        return

    if not Path(app.config["DATABASE"]).exists():
        init_db()
        with app.app_context():
            seed_default_data()

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
