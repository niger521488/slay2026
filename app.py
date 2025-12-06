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
        "title": "Лучший музыкальный артист",
        "description": "Артисты, чьи треки звучали чаще всего в этом году.",
        "nominees": [
            {
                "name": "Nova Light",
                "description": "Электронный продюсер с новым взглядом на EDM.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=Nova+Light",
            },
            {
                "name": "Маяк",
                "description": "Инди-группа, которая покорила фестивали летом.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%9C%D0%B0%D1%8F%D0%BA",
            },
            {
                "name": "RAPID",
                "description": "Хип-хоп исполнитель с сильными текстами.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=RAPID",
            },
        ],
    },
    {
        "title": "Дебют года",
        "description": "Новички, которые громко заявили о себе.",
        "nominees": [
            {
                "name": "Север",
                "description": "Альтернативный исполнитель с атмосферными клипами.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%A1%D0%B5%D0%B2%D0%B5%D1%80",
            },
            {
                "name": "LUNA",
                "description": "Поп-певица с футуристичным звучанием.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=LUNA",
            },
            {
                "name": "Орбита",
                "description": "Группа, совмещающая рок и электронику.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%9E%D1%80%D0%B1%D0%B8%D1%82%D0%B0",
            },
        ],
    },
    {
        "title": "Лучшее шоу",
        "description": "Сценические постановки, которые впечатлили визуально.",
        "nominees": [
            {
                "name": "Дыхание города",
                "description": "Иммерсивное шоу со световыми инсталляциями.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%94%D1%8B%D1%85%D0%B0%D0%BD%D0%B8%D0%B5+%D0%B3%D0%BE%D1%80%D0%BE%D0%B4%D0%B0",
            },
            {
                "name": "Эхо",
                "description": "Театральный перформанс с AR-элементами.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%AD%D1%85%D0%BE",
            },
            {
                "name": "Вихрь",
                "description": "Шоу-дронов над набережной.",
                "photo_url": "https://via.placeholder.com/320x200.png?text=%D0%92%D0%B8%D1%85%D1%80%D1%8C",
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
                    nominee["description"],
                    nominee["photo_url"],
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
