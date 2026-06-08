"""SQLite database layer for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "bolao.db"

PHASES = [
    "Fase de Grupos",
    "32 avos",
    "Oitavas",
    "Quartas",
    "Semifinais",
    "Terceiro Lugar",
    "Final",
]

PHASE_STATUS = ["Não iniciada", "Aberta", "Fechada", "Finalizada"]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'participant')),
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS phases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'Não iniciada',
                sort_order INTEGER NOT NULL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id INTEGER NOT NULL,
                team_home TEXT NOT NULL,
                team_away TEXT NOT NULL,
                game_datetime TEXT,
                group_name TEXT,
                home_score INTEGER,
                away_score INTEGER,
                finished INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                home_score INTEGER NOT NULL,
                away_score INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, game_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                home_score INTEGER NOT NULL,
                away_score INTEGER NOT NULL,
                version INTEGER NOT NULL,
                saved_at TEXT NOT NULL,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS special_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                champion TEXT,
                vice TEXT,
                top_scorer TEXT,
                points_champion INTEGER NOT NULL DEFAULT 0,
                points_vice INTEGER NOT NULL DEFAULT 0,
                points_scorer INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS special_prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                special_prediction_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                champion TEXT,
                vice TEXT,
                top_scorer TEXT,
                version INTEGER NOT NULL,
                saved_at TEXT NOT NULL,
                FOREIGN KEY (special_prediction_id) REFERENCES special_predictions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tournament_settings (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                champion_team TEXT,
                vice_team TEXT,
                top_scorers TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ranking_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total_points INTEGER NOT NULL,
                position INTEGER NOT NULL,
                snapshot_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS c FROM phases").fetchone()["c"]
        if existing == 0:
            now = datetime.now().isoformat()
            for i, name in enumerate(PHASES):
                conn.execute(
                    "INSERT INTO phases (name, status, sort_order, updated_at) VALUES (?, ?, ?, ?)",
                    (name, "Não iniciada", i + 1, now),
                )

        conn.execute(
            "INSERT OR IGNORE INTO tournament_settings (id, updated_at) VALUES (1, ?)",
            (datetime.now().isoformat(),),
        )


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def now_iso() -> str:
    return datetime.now().isoformat()


# --- Users ---


def count_admins() -> int:
    with db_session() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND active = 1"
        ).fetchone()["c"]


def create_user(username: str, password_hash: str, full_name: str, role: str) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, password_hash, full_name, role, now_iso()),
        )
        return cur.lastrowid


def get_user_by_username(username: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


def list_participants() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, username, full_name, role, active, created_at
            FROM users WHERE role = 'participant'
            ORDER BY full_name
            """
        ).fetchall()
        return rows_to_list(rows)


def set_user_active(user_id: int, active: bool):
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET active = ? WHERE id = ? AND role = 'participant'",
            (1 if active else 0, user_id),
        )


def update_user_password(user_id: int, password_hash: str):
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )


# --- Phases ---


def list_phases() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM phases ORDER BY sort_order"
        ).fetchall()
        return rows_to_list(rows)


def get_phase(phase_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM phases WHERE id = ?", (phase_id,)).fetchone()
        return row_to_dict(row)


def get_phase_by_name(name: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM phases WHERE name = ?", (name,)).fetchone()
        return row_to_dict(row)


def update_phase_status(phase_id: int, status: str):
    with db_session() as conn:
        conn.execute(
            "UPDATE phases SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), phase_id),
        )


# --- Games ---


def create_game(
    phase_id: int,
    team_home: str,
    team_away: str,
    game_datetime: str | None = None,
    group_name: str | None = None,
) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO games (phase_id, team_home, team_away, game_datetime, group_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (phase_id, team_home.strip(), team_away.strip(), game_datetime, group_name, now_iso()),
        )
        return cur.lastrowid


def list_games(phase_id: int | None = None) -> list[dict]:
    with db_session() as conn:
        if phase_id:
            rows = conn.execute(
                """
                SELECT DISTINCT g.*, p.name AS phase_name, p.status AS phase_status
                FROM games g
                JOIN phases p ON p.id = g.phase_id
                WHERE g.phase_id = ?
                ORDER BY g.game_datetime, g.id
                """,
                (phase_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT g.*, p.name AS phase_name, p.status AS phase_status
                FROM games g
                JOIN phases p ON p.id = g.phase_id
                ORDER BY p.sort_order, g.game_datetime, g.id
                """
            ).fetchall()
        return rows_to_list(rows)


def get_game(game_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT g.*, p.name AS phase_name, p.status AS phase_status
            FROM games g
            JOIN phases p ON p.id = g.phase_id
            WHERE g.id = ?
            """,
            (game_id,),
        ).fetchone()
        return row_to_dict(row)


def update_game_result(game_id: int, home_score: int, away_score: int):
    with db_session() as conn:
        conn.execute(
            """
            UPDATE games
            SET home_score = ?, away_score = ?, finished = 1
            WHERE id = ?
            """,
            (home_score, away_score, game_id),
        )


def delete_game(game_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))


# --- Predictions ---


def save_prediction(user_id: int, game_id: int, home_score: int, away_score: int) -> dict:
    ts = now_iso()
    with db_session() as conn:
        existing = conn.execute(
            "SELECT * FROM predictions WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
        ).fetchone()

        if existing:
            new_version = existing["version"] + 1
            conn.execute(
                """
                UPDATE predictions
                SET home_score = ?, away_score = ?, version = ?, updated_at = ?
                WHERE id = ?
                """,
                (home_score, away_score, new_version, ts, existing["id"]),
            )
            pred_id = existing["id"]
            version = new_version
        else:
            cur = conn.execute(
                """
                INSERT INTO predictions (user_id, game_id, home_score, away_score, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, game_id, home_score, away_score, ts, ts),
            )
            pred_id = cur.lastrowid
            version = 1

        conn.execute(
            """
            INSERT INTO prediction_history
            (prediction_id, user_id, game_id, home_score, away_score, version, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (pred_id, user_id, game_id, home_score, away_score, version, ts),
        )

        row = conn.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,)).fetchone()
        return row_to_dict(row)


def update_prediction_points(prediction_id: int, points: int):
    with db_session() as conn:
        conn.execute(
            "UPDATE predictions SET points = ? WHERE id = ?", (points, prediction_id)
        )


def get_user_predictions(user_id: int, phase_id: int | None = None) -> list[dict]:
    with db_session() as conn:
        if phase_id:
            rows = conn.execute(
                """
                SELECT pr.*, g.team_home, g.team_away, g.home_score AS result_home,
                       g.away_score AS result_away, g.finished, g.game_datetime,
                       g.phase_id, p.name AS phase_name, p.status AS phase_status
                FROM predictions pr
                JOIN games g ON g.id = pr.game_id
                JOIN phases p ON p.id = g.phase_id
                WHERE pr.user_id = ? AND g.phase_id = ?
                ORDER BY g.game_datetime, g.id
                """,
                (user_id, phase_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT pr.*, g.team_home, g.team_away, g.home_score AS result_home,
                       g.away_score AS result_away, g.finished, g.game_datetime,
                       g.phase_id, p.name AS phase_name, p.status AS phase_status
                FROM predictions pr
                JOIN games g ON g.id = pr.game_id
                JOIN phases p ON p.id = g.phase_id
                WHERE pr.user_id = ?
                ORDER BY p.sort_order, g.game_datetime, g.id
                """,
                (user_id,),
            ).fetchall()
        return rows_to_list(rows)


def get_predictions_for_game(game_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT pr.*, u.full_name, u.username
            FROM predictions pr
            JOIN users u ON u.id = pr.user_id
            WHERE pr.game_id = ?
            ORDER BY u.full_name
            """,
            (game_id,),
        ).fetchall()
        return rows_to_list(rows)


def get_all_predictions(phase_id: int | None = None) -> list[dict]:
    with db_session() as conn:
        if phase_id:
            rows = conn.execute(
                """
                SELECT pr.*, u.full_name, u.username, g.team_home, g.team_away,
                       g.home_score AS result_home, g.away_score AS result_away,
                       g.finished, g.phase_id, p.name AS phase_name
                FROM predictions pr
                JOIN users u ON u.id = pr.user_id
                JOIN games g ON g.id = pr.game_id
                JOIN phases p ON p.id = g.phase_id
                WHERE g.phase_id = ?
                ORDER BY u.full_name, g.game_datetime
                """,
                (phase_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT pr.*, u.full_name, u.username, g.team_home, g.team_away,
                       g.home_score AS result_home, g.away_score AS result_away,
                       g.finished, g.phase_id, p.name AS phase_name
                FROM predictions pr
                JOIN users u ON u.id = pr.user_id
                JOIN games g ON g.id = pr.game_id
                JOIN phases p ON p.id = g.phase_id
                ORDER BY p.sort_order, u.full_name, g.game_datetime
                """
            ).fetchall()
        return rows_to_list(rows)


def get_prediction_history(user_id: int, game_id: int | None = None) -> list[dict]:
    with db_session() as conn:
        if game_id:
            rows = conn.execute(
                """
                SELECT h.*, g.team_home, g.team_away
                FROM prediction_history h
                JOIN games g ON g.id = h.game_id
                WHERE h.user_id = ? AND h.game_id = ?
                ORDER BY h.version DESC
                """,
                (user_id, game_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.*, g.team_home, g.team_away
                FROM prediction_history h
                JOIN games g ON g.id = h.game_id
                WHERE h.user_id = ?
                ORDER BY h.saved_at DESC
                """,
                (user_id,),
            ).fetchall()
        return rows_to_list(rows)


# --- Special predictions ---


def save_special_prediction(
    user_id: int, champion: str, vice: str, top_scorer: str
) -> dict:
    ts = now_iso()
    with db_session() as conn:
        existing = conn.execute(
            "SELECT * FROM special_predictions WHERE user_id = ?", (user_id,)
        ).fetchone()

        if existing:
            new_version = existing["version"] + 1
            conn.execute(
                """
                UPDATE special_predictions
                SET champion = ?, vice = ?, top_scorer = ?, version = ?, updated_at = ?
                WHERE id = ?
                """,
                (champion.strip(), vice.strip(), top_scorer.strip(), new_version, ts, existing["id"]),
            )
            sp_id = existing["id"]
            version = new_version
        else:
            cur = conn.execute(
                """
                INSERT INTO special_predictions
                (user_id, champion, vice, top_scorer, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, champion.strip(), vice.strip(), top_scorer.strip(), ts, ts),
            )
            sp_id = cur.lastrowid
            version = 1

        conn.execute(
            """
            INSERT INTO special_prediction_history
            (special_prediction_id, user_id, champion, vice, top_scorer, version, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sp_id, user_id, champion.strip(), vice.strip(), top_scorer.strip(), version, ts),
        )

        row = conn.execute(
            "SELECT * FROM special_predictions WHERE id = ?", (sp_id,)
        ).fetchone()
        return row_to_dict(row)


def get_special_prediction(user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM special_predictions WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row_to_dict(row)


def get_all_special_predictions() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT sp.*, u.full_name, u.username
            FROM special_predictions sp
            JOIN users u ON u.id = sp.user_id
            ORDER BY u.full_name
            """
        ).fetchall()
        return rows_to_list(rows)


def update_special_points(
    user_id: int,
    points_champion: int,
    points_vice: int,
    points_scorer: int,
):
    with db_session() as conn:
        conn.execute(
            """
            UPDATE special_predictions
            SET points_champion = ?, points_vice = ?, points_scorer = ?
            WHERE user_id = ?
            """,
            (points_champion, points_vice, points_scorer, user_id),
        )


def get_special_prediction_history(user_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT * FROM special_prediction_history
            WHERE user_id = ?
            ORDER BY version DESC
            """,
            (user_id,),
        ).fetchall()
        return rows_to_list(rows)


# --- Tournament settings ---


def get_tournament_settings() -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM tournament_settings WHERE id = 1").fetchone()
        return row_to_dict(row)


def update_tournament_settings(champion: str, vice: str, top_scorers: str):
    with db_session() as conn:
        conn.execute(
            """
            UPDATE tournament_settings
            SET champion_team = ?, vice_team = ?, top_scorers = ?, updated_at = ?
            WHERE id = 1
            """,
            (champion.strip(), vice.strip(), top_scorers.strip(), now_iso()),
        )


# --- Ranking snapshots ---


def save_ranking_snapshot(user_id: int, total_points: int, position: int):
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO ranking_snapshots (user_id, total_points, position, snapshot_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, total_points, position, now_iso()),
        )


def get_latest_snapshots() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT rs.*
            FROM ranking_snapshots rs
            INNER JOIN (
                SELECT user_id, MAX(snapshot_at) AS max_at
                FROM ranking_snapshots
                GROUP BY user_id
            ) latest ON latest.user_id = rs.user_id AND latest.max_at = rs.snapshot_at
            """
        ).fetchall()
        return rows_to_list(rows)


def get_earliest_snapshots() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT rs.*
            FROM ranking_snapshots rs
            INNER JOIN (
                SELECT user_id, MIN(snapshot_at) AS min_at
                FROM ranking_snapshots
                GROUP BY user_id
            ) earliest ON earliest.user_id = rs.user_id AND earliest.min_at = rs.snapshot_at
            """
        ).fetchall()
        return rows_to_list(rows)
