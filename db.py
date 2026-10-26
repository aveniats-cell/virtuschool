import os
import json
import libsql_client

_client = None


def _get():
    global _client
    if _client is None:
        _client = libsql_client.create_client_sync(
            url=os.getenv("TURSO_DATABASE_URL"),
            auth_token=os.getenv("TURSO_AUTH_TOKEN"),
        )
    return _client


def q(sql, params=()):
    """SELECT → список строк."""
    return _get().execute(sql, params).rows


def q1(sql, params=()):
    """SELECT → первая строка или None."""
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql, params=()):
    """INSERT / UPDATE / DELETE / DDL."""
    _get().execute(sql, params)


# ============== СХЕМА ==============

def init_schema():
    ex("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            gender TEXT,
            self_rating INTEGER,
            mode TEXT,
            group_id INTEGER,
            role TEXT DEFAULT 'student',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            payload TEXT,
            group_id INTEGER,
            is_homework INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            assignment_id INTEGER,
            answer TEXT,
            is_correct INTEGER,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, assignment_id)
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            value INTEGER,
            comment TEXT,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            when_text TEXT,
            where_text TEXT,
            group_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ex("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)


# ============== НАСТРОЙКИ / АДМИН ==============

def get_setting(key, default=None):
    row = q1("SELECT value FROM settings WHERE key = ?", (key,))
    return row[0] if row else default


def set_setting(key, value):
    ex("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


def get_admin_id():
    v = get_setting("admin_id")
    return int(v) if v else 0


def set_admin_id(user_id):
    set_setting("admin_id", int(user_id))


def is_admin(user_id: int) -> bool:
    return user_id == get_admin_id()


def admin_username() -> str:
    return (os.getenv("ADMIN_USERNAME") or "").lstrip("@").lower()


def user_is_admin(tg_user) -> bool:
    """Проверка админа по id + по username из Values (на случай переезда)."""
    if tg_user.id == get_admin_id():
        return True
    if admin_username() and tg_user.username:
        if tg_user.username.lstrip("@").lower() == admin_username():
            if not get_admin_id():
                set_admin_id(tg_user.id)
            return True
    return False


# ============== ПОЛЬЗОВАТЕЛИ ==============

def get_user(user_id):
    return q1(
        "SELECT user_id, name, gender, self_rating, mode, group_id, role "
        "FROM users WHERE user_id = ?",
        (user_id,),
    )


def create_user(user_id, name, gender, self_rating, mode):
    ex(
        "INSERT OR REPLACE INTO users (user_id, name, gender, self_rating, mode, role) "
        "VALUES (?, ?, ?, ?, ?, 'student')",
        (user_id, name, gender, self_rating, mode),
    )


def set_user_group(user_id, group_id):
    ex("UPDATE users SET group_id = ? WHERE user_id = ?", (group_id, user_id))


def set_user_role(user_id, role):
    ex("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))


def pending_students():
    return q(
        "SELECT user_id, name FROM users "
        "WHERE role = 'student' AND group_id IS NULL ORDER BY created_at"
    )


# ============== ГРУППЫ ==============

def get_or_create_group(name):
    ex("INSERT OR IGNORE INTO groups (name) VALUES (?)", (name,))
    row = q1("SELECT id FROM groups WHERE name = ?", (name,))
    return row[0]


def list_groups():
    return q("SELECT id, name FROM groups ORDER BY name")


def get_group(group_id):
    return q1("SELECT id, name FROM groups WHERE id = ?", (group_id,))


def list_students(group_id=None):
    if group_id is None:
        return q(
            "SELECT user_id, name, group_id FROM users "
            "WHERE role = 'student' ORDER BY name"
        )
    return q(
        "SELECT user_id, name, group_id FROM users "
        "WHERE role = 'student' AND group_id = ? ORDER BY name",
        (group_id,),
    )


def students_not_in_group(group_id):
    return q(
        "SELECT user_id, name, group_id FROM users "
        "WHERE role = 'student' AND (group_id IS NULL OR group_id != ?) ORDER BY name",
        (group_id,),
    )


# ============== ОЦЕНКИ ==============

def weighted_avg(user_id):
    rows = q("SELECT value, source FROM grades WHERE user_id = ?", (user_id,))
    if not rows:
        return None
    weights = {"video": 3, "homework": 2, "lesson": 1}
    total_w = 0
    total = 0
    for value, source in rows:
        w = weights.get(source or "lesson", 1)
        total += value * w
        total_w += w
    return round(total / total_w, 2) if total_w else None


def last_grades(user_id, limit=10):
    return q(
        "SELECT value, comment, source, created_at FROM grades "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )


def create_grade(user_id, value, comment, source):
    ex(
        "INSERT INTO grades (user_id, value, comment, source) VALUES (?, ?, ?, ?)",
        (user_id, value, comment, source),
    )


# ============== ЗАДАНИЯ ==============

def create_assignment(atype, payload_dict, group_id, is_homework=False):
    ex(
        "INSERT INTO assignments (type, payload, group_id, is_homework) "
        "VALUES (?, ?, ?, ?)",
        (atype, json.dumps(payload_dict, ensure_ascii=False), group_id, 1 if is_homework else 0),
    )


def get_assignment(assignment_id):
    return q1(
        "SELECT id, type, payload, group_id, is_homework FROM assignments WHERE id = ?",
        (assignment_id,),
    )


def assignments_for_user(user_id, homework=False):
    user = get_user(user_id)
    if not user or user[5] is None:
        return []
    return q(
        "SELECT id, type, payload, is_homework FROM assignments "
        "WHERE group_id = ? AND is_homework = ? ORDER BY id DESC",
        (user[5], 1 if homework else 0),
    )


def assignments_in_group(group_id, homework=False):
    return q(
        "SELECT id, type, payload, is_homework FROM assignments "
        "WHERE group_id = ? AND is_homework = ? ORDER BY id DESC",
        (group_id, 1 if homework else 0),
    )


def latest_homework(user_id):
    rows = assignments_for_user(user_id, homework=True)
    return rows[0] if rows else None


def delete_assignment(assignment_id):
    ex("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    ex("DELETE FROM submissions WHERE assignment_id = ?", (assignment_id,))


# ============== ОТВЕТЫ ==============

def has_submission(user_id, assignment_id):
    return q1(
        "SELECT is_correct, answer FROM submissions WHERE user_id = ? AND assignment_id = ?",
        (user_id, assignment_id),
    )


def save_submission(user_id, assignment_id, answer, is_correct):
    ex(
        "INSERT OR REPLACE INTO submissions (user_id, assignment_id, answer, is_correct) "
        "VALUES (?, ?, ?, ?)",
        (user_id, assignment_id, answer, 1 if is_correct else 0),
    )


def done_count(user_id):
    row = q1("SELECT COUNT(*) FROM submissions WHERE user_id = ?", (user_id,))
    return row[0]


def student_progress(user_id):
    user = get_user(user_id)
    if not user or user[5] is None:
        return []
    return q(
        "SELECT a.id, a.type, a.is_homework, s.is_correct "
        "FROM assignments a "
        "LEFT JOIN submissions s "
        "  ON s.assignment_id = a.id AND s.user_id = ? "
        "WHERE a.group_id = ? "
        "ORDER BY a.id DESC",
        (user_id, user[5]),
    )


# ============== АНОНСЫ ==============

def create_announcement(text, when_text, where_text, group_id):
    ex(
        "INSERT INTO announcements (text, when_text, where_text, group_id) "
        "VALUES (?, ?, ?, ?)",
        (text, when_text, where_text, group_id),
    )


def latest_announcement(user_id):
    user = get_user(user_id)
    if not user:
        return None
    return q1(
        "SELECT text, when_text, where_text FROM announcements "
        "WHERE group_id IS NULL OR group_id = ? ORDER BY id DESC LIMIT 1",
        (user[5],),
    )


# ============== СЛУЖЕБНОЕ ==============

def all_student_ids():
    return [r[0] for r in q("SELECT user_id FROM users WHERE role = 'student'")]
