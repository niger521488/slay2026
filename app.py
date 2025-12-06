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


DEFAULT_NOMINATIONS = [
    {
        "title": "King года",
        "description": "Человек, который всегда ведет себя так, будто он главный и все это поддерживают.",
        "nominees": [
            {
                "name": "Король сценария",
                "description": "Всегда берет лидерство и задаёт тон компании.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=King+1",
            },
            {
                "name": "Командир",
                "description": "Организует процессы и направляет остальных.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=King+2",
            },
            {
                "name": "Шеф",
                "description": "Всегда знает, что делать, и другие следуют.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=King+3",
            },
        ],
    },
    {
        "title": "Queen года",
        "description": "Персона с эффектной подачей: стиль, эмоции, эмоции, жесты.",
        "nominees": [
            {
                "name": "Икона",
                "description": "Всегда эффектна и умеет подать себя.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Queen+1",
            },
            {
                "name": "Дива",
                "description": "Эмоции, жесты и харизма на максимум.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Queen+2",
            },
            {
                "name": "Муза",
                "description": "Задаёт стиль и вдохновляет окружающих.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Queen+3",
            },
        ],
    },
    {
        "title": "Мем года",
        "description": "Источник самых смешных моментов года.",
        "nominees": [
            {
                "name": "Легендарная шутка",
                "description": "Фраза, которую цитируют снова и снова.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Meme+1",
            },
            {
                "name": "Гэг недели",
                "description": "Всегда вовремя вставляет смешной момент.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Meme+2",
            },
            {
                "name": "Вечный мем",
                "description": "Шутка, которая стала частью разговоров.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Meme+3",
            },
        ],
    },
    {
        "title": "Человек-мем года",
        "description": "Главный генератор мемов.",
        "nominees": [
            {
                "name": "Герой шуток",
                "description": "Превращает любое событие в смешной мем.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Memer+1",
            },
            {
                "name": "Создатель смеха",
                "description": "Придумывает новые форматы и приколы.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Memer+2",
            },
            {
                "name": "Главный вайбер",
                "description": "Делает чат смешным каждый день.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Memer+3",
            },
        ],
    },
    {
        "title": "Нон актив года",
        "description": "Тот, кого как будто «нету».",
        "nominees": [
            {
                "name": "Тихий наблюдатель",
                "description": "Редко пишет, но всегда в теме.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Silent+1",
            },
            {
                "name": "Призрак чата",
                "description": "Присутствует, но не проявляется.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Silent+2",
            },
            {
                "name": "Скрытый читатель",
                "description": "Всегда читает, почти не пишет.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Silent+3",
            },
        ],
    },
    {
        "title": "Долбоеб года",
        "description": "Без объяснений.",
        "nominees": [
            {
                "name": "Случайный герой",
                "description": "Главный источник фейлов года.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Facepalm+1",
            },
            {
                "name": "Хаос-мейкер",
                "description": "Создаёт абсурдные ситуации.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Facepalm+2",
            },
            {
                "name": "Эпичный ляп",
                "description": "За серию нелепых решений.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Facepalm+3",
            },
        ],
    },
    {
        "title": "Харизма года",
        "description": "Человек, который просто появляется — и настроение у всех становится лучше.",
        "nominees": [
            {
                "name": "Солнечный",
                "description": "Приносит тепло и улыбки.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Charisma+1",
            },
            {
                "name": "Магнетический",
                "description": "Притягивает внимание и вдохновение.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Charisma+2",
            },
            {
                "name": "Вдохновитель",
                "description": "Поднимает настроение одним появлением.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Charisma+3",
            },
        ],
    },
    {
        "title": "Пунктуальность года",
        "description": "Без объяснений.",
        "nominees": [
            {
                "name": "Тайм-менеджер",
                "description": "Приходит вовремя и напоминает другим.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Punctual+1",
            },
            {
                "name": "Ровно в час",
                "description": "Всегда к дедлайну, без опозданий.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Punctual+2",
            },
            {
                "name": "Секундомер",
                "description": "Знает цену минутам.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Punctual+3",
            },
        ],
    },
    {
        "title": "Токсик года",
        "description": "Мастер колких комментариев и пассивной агрессии.",
        "nominees": [
            {
                "name": "Сарказм мастер",
                "description": "Колкие реплики в любой ситуации.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Toxic+1",
            },
            {
                "name": "Ироничный",
                "description": "Любит поддеть и уколоть.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Toxic+2",
            },
            {
                "name": "Пассивный агрессор",
                "description": "Комменты с перчинкой.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Toxic+3",
            },
        ],
    },
    {
        "title": "Лентяй года",
        "description": "Тот, которому всегда лень.",
        "nominees": [
            {
                "name": "Соня",
                "description": "Любит отложить дела на завтра.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Lazy+1",
            },
            {
                "name": "Прокрастинатор",
                "description": "Всегда найдёт повод ничего не делать.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Lazy+2",
            },
            {
                "name": "Диванный эксперт",
                "description": "Комментирует, но не делает.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Lazy+3",
            },
        ],
    },
    {
        "title": "Актив года",
        "description": "Самый активный участник группы, инициатор.",
        "nominees": [
            {
                "name": "Двигатель",
                "description": "Запускает новые инициативы.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Active+1",
            },
            {
                "name": "Организатор",
                "description": "Собирает всех на события и обсуждения.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Active+2",
            },
            {
                "name": "Катализатор",
                "description": "Подталкивает к действиям и решениям.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Active+3",
            },
        ],
    },
    {
        "title": "Завоз года",
        "description": "Тот, кто внезапно завёз лучший вайб, идеи, шутки или стиль.",
        "nominees": [
            {
                "name": "Вайбмейкер",
                "description": "Привнёс лучшие настроения.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Vibe+1",
            },
            {
                "name": "Идейный драйвер",
                "description": "Подкинул свежие идеи и шутки.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Vibe+2",
            },
            {
                "name": "Стилевик",
                "description": "Привёз стиль и настроение.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Vibe+3",
            },
        ],
    },
]


def seed_default_data():
    db = get_db()
    existing = db.execute("SELECT COUNT(*) AS total FROM nominations").fetchone()
    if existing["total"] > 0:
        return

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

    data: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        data.setdefault(row["nomination_title"], []).append(row)
    return render_template("admin.html", results=data)


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
