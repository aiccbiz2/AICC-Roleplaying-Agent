"""SQLite 데이터베이스 초기화 + CRUD 헬퍼"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import bcrypt

from config import DB_PATH

# ── KST 타임존 헬퍼 ──────────────────────────────────────
# DB는 SQLite의 CURRENT_TIMESTAMP로 UTC 시각을 저장한다 (스키마가 이미 그렇게 생성됨).
# 응답할 때 UTC → KST 변환 + ISO 8601 +09:00 타임존을 명시하여
# JavaScript new Date()가 정확히 파싱할 수 있도록 한다.

from datetime import datetime as _dt, timedelta as _td, timezone as _tz

_KST = _tz(_td(hours=9))
_UTC = _tz.utc

_KST_FIELDS = (
    "created_at", "ended_at", "started_at", "answered_at",
    "last_active", "updated_at",
)


def _to_kst_iso(value) -> str | None:
    """SQLite 'YYYY-MM-DD HH:MM:SS' (UTC, timezone 없음)
    → KST 변환 후 ISO 8601 'YYYY-MM-DDTHH:MM:SS+09:00' 형식 반환.

    이미 타임존 정보가 있으면 그대로 둔다.
    """
    if not value:
        return value
    s = str(value).strip()

    # 이미 timezone 정보가 있으면 (Z 또는 +09:00 등) 그대로
    if s.endswith("Z") or (len(s) > 10 and ("+" in s[10:] or s[10:].count("-") > 0)):
        return s

    # SQLite naive datetime을 UTC로 해석 → KST로 변환
    try:
        # "YYYY-MM-DD HH:MM:SS" 또는 "YYYY-MM-DDTHH:MM:SS"
        normalized = s.replace("T", " ")
        # 마이크로초 포함 가능 ("2026-04-08 06:06:51.123")
        if "." in normalized:
            naive = _dt.strptime(normalized, "%Y-%m-%d %H:%M:%S.%f")
        else:
            naive = _dt.strptime(normalized, "%Y-%m-%d %H:%M:%S")
        utc_aware = naive.replace(tzinfo=_UTC)
        kst = utc_aware.astimezone(_KST)
        return kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except Exception:
        # 파싱 실패 시 원본 + 타임존만 추가 (안전 fallback)
        if "T" not in s and " " in s:
            s = s.replace(" ", "T")
        return s + "+09:00"


def _with_kst(d: dict) -> dict:
    """dict의 모든 datetime 필드(_KST_FIELDS)를 UTC → KST ISO 형식으로 변환"""
    for key in _KST_FIELDS:
        if key in d and d[key]:
            d[key] = _to_kst_iso(d[key])
    return d


# ── 초기화 ──────────────────────────────────────────────

# 스레드-로컬 커넥션 풀: 스레드별로 하나의 연결만 유지
_local = threading.local()


def _connect() -> sqlite3.Connection:
    """스레드-로컬 SQLite 연결 (스레드당 1개 연결 재사용)"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            # 연결이 닫힌 경우 재생성
            pass

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    _local.conn = conn
    return conn


def init_db():
    """테이블 생성 + 관리자 시드"""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            position TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT (datetime('now', '+9 hours'))
        );

        CREATE TABLE IF NOT EXISTS roleplay_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            scenario_key TEXT NOT NULL,
            scenario_title TEXT NOT NULL,
            persona_level TEXT NOT NULL,
            overall_grade TEXT,
            conversation TEXT NOT NULL,
            feedback TEXT,
            turn_count INTEGER,
            started_at DATETIME,
            ended_at DATETIME DEFAULT (datetime('now', '+9 hours')),
            duration_seconds INTEGER
        );

        CREATE TABLE IF NOT EXISTS quiz_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            question TEXT NOT NULL,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN,
            answered_at DATETIME DEFAULT (datetime('now', '+9 hours'))
        );

        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            action TEXT NOT NULL,
            page TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at DATETIME DEFAULT (datetime('now', '+9 hours'))
        );

        CREATE INDEX IF NOT EXISTS idx_roleplay_user ON roleplay_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_quiz_user ON quiz_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_access_user ON access_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_access_created ON access_logs(created_at);
    """)
    conn.commit()
    _seed_admin(conn)


def _seed_admin(conn: sqlite3.Connection):
    """관리자 계정이 없으면 생성"""
    row = conn.execute("SELECT id FROM users WHERE id = ?", ("admin",)).fetchone()
    if row:
        return
    pw_hash = bcrypt.hashpw("admin1234".encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (id, password_hash, name, department, position, role) VALUES (?, ?, ?, ?, ?, ?)",
        ("admin", pw_hash, "양준모", "AI사업2팀", "팀장", "admin"),
    )
    conn.commit()


# ── 사용자 CRUD ─────────────────────────────────────────

def get_user(user_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_user(user_id: str, password: str, name: str, department: str, position: str, role: str = "user") -> dict:
    conn = _connect()
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (id, password_hash, name, department, position, role) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, pw_hash, name, department, position, role),
    )
    conn.commit()
    return get_user(user_id)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def change_password(user_id: str, new_password: str) -> bool:
    conn = _connect()
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
    conn.commit()
    return True


# ── 롤플레이 세션 ──────────────────────────────────────

def save_roleplay_session(
    user_id: str,
    scenario_key: str,
    scenario_title: str,
    persona_level: str,
    overall_grade: str | None,
    conversation: list[dict],
    feedback: dict | None,
    turn_count: int,
    started_at: str | None,
    duration_seconds: int | None,
) -> int:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO roleplay_sessions
           (user_id, scenario_key, scenario_title, persona_level, overall_grade,
            conversation, feedback, turn_count, started_at, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, scenario_key, scenario_title, persona_level, overall_grade,
            json.dumps(conversation, ensure_ascii=False),
            json.dumps(feedback, ensure_ascii=False) if feedback else None,
            turn_count, started_at, duration_seconds,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_user_roleplay_sessions(user_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """SELECT id, scenario_key, scenario_title, persona_level, overall_grade,
                  turn_count, started_at, ended_at, duration_seconds
           FROM roleplay_sessions WHERE user_id = ? ORDER BY ended_at DESC""",
        (user_id,),
    ).fetchall()
    return [_with_kst(dict(r)) for r in rows]


def get_roleplay_detail(session_id: int, user_id: str | None = None) -> dict | None:
    conn = _connect()
    if user_id:
        row = conn.execute(
            "SELECT * FROM roleplay_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM roleplay_sessions WHERE id = ?", (session_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["conversation"] = json.loads(d["conversation"]) if d["conversation"] else []
    d["feedback"] = json.loads(d["feedback"]) if d["feedback"] else None
    return _with_kst(d)


def update_roleplay_session(
    session_id: int,
    user_id: str,
    conversation: list[dict] | None = None,
    feedback: dict | None = None,
    overall_grade: str | None = None,
    turn_count: int | None = None,
    duration_seconds: int | None = None,
) -> bool:
    """기존 롤플레이 세션 업데이트 (대화 내용, 피드백, 등급 등)"""
    conn = _connect()
    fields = []
    values = []
    if conversation is not None:
        fields.append("conversation = ?")
        values.append(json.dumps(conversation, ensure_ascii=False))
    if feedback is not None:
        fields.append("feedback = ?")
        values.append(json.dumps(feedback, ensure_ascii=False))
    if overall_grade is not None:
        fields.append("overall_grade = ?")
        values.append(overall_grade)
    if turn_count is not None:
        fields.append("turn_count = ?")
        values.append(turn_count)
    if duration_seconds is not None:
        fields.append("duration_seconds = ?")
        values.append(duration_seconds)

    if not fields:
        return False

    fields.append("ended_at = datetime('now', '+9 hours')")
    values.extend([session_id, user_id])

    sql = f"UPDATE roleplay_sessions SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
    cur = conn.execute(sql, values)
    conn.commit()
    return cur.rowcount > 0


# ── 퀴즈 기록 ──────────────────────────────────────────

def save_quiz_record(
    user_id: str,
    category: str,
    difficulty: str,
    question: str,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
) -> int:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO quiz_records
           (user_id, category, difficulty, question, user_answer, correct_answer, is_correct)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, category, difficulty, question, user_answer, correct_answer, is_correct),
    )
    conn.commit()
    return cur.lastrowid


def get_user_quiz_records(user_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """SELECT id, category, difficulty, question, user_answer, correct_answer, is_correct, answered_at
           FROM quiz_records WHERE user_id = ? ORDER BY answered_at DESC""",
        (user_id,),
    ).fetchall()
    return [_with_kst(dict(r)) for r in rows]


# ── 개인 대시보드 통계 ─────────────────────────────────

def get_user_dashboard_stats(user_id: str) -> dict:
    conn = _connect()
    # 주간 롤플레이 완료 수
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM roleplay_sessions
           WHERE user_id = ? AND ended_at >= datetime('now', '+9 hours', '-7 days')""",
        (user_id,),
    ).fetchone()
    roleplay_count = row["cnt"] if row else 0

    # 주간 퀴즈 정답률
    row = conn.execute(
        """SELECT COUNT(*) as total, SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct
           FROM quiz_records
           WHERE user_id = ? AND answered_at >= datetime('now', '+9 hours', '-7 days')""",
        (user_id,),
    ).fetchone()
    quiz_total = row["total"] if row else 0
    quiz_correct = row["correct"] or 0
    quiz_accuracy = round(100 * quiz_correct / quiz_total) if quiz_total > 0 else 0

    # 학습 용어 수 (퀴즈 푼 고유 질문 수)
    row = conn.execute(
        "SELECT COUNT(DISTINCT question) as cnt FROM quiz_records WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    terms_learned = row["cnt"] if row else 0

    # 연속 학습일 (최근 연속으로 활동한 날 수)
    rows = conn.execute(
        """SELECT DISTINCT DATE(created_at) as d FROM access_logs
           WHERE user_id = ? ORDER BY d DESC""",
        (user_id,),
    ).fetchall()
    streak = 0
    if rows:
        from datetime import date, timedelta
        today = date.today()
        for i, r in enumerate(rows):
            day = date.fromisoformat(r["d"])
            if day == today - timedelta(days=i):
                streak += 1
            else:
                break

    return {
        "roleplay_count": roleplay_count,
        "quiz_accuracy": quiz_accuracy,
        "terms_learned": terms_learned,
        "streak_days": streak,
    }


# ── 접속 로그 ──────────────────────────────────────────

def log_access(user_id: str, action: str, page: str | None = None, ip_address: str | None = None, user_agent: str | None = None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO access_logs (user_id, action, page, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, page, ip_address, user_agent),
    )
    conn.commit()
    return cur.lastrowid


# ── 관리자용 집계 ──────────────────────────────────────

def get_overview_stats() -> dict:
    conn = _connect()
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
    total_roleplay = conn.execute("SELECT COUNT(*) FROM roleplay_sessions").fetchone()[0]
    total_quiz = conn.execute("SELECT COUNT(*) FROM quiz_records").fetchone()[0]

    week_active = conn.execute("""
        SELECT COUNT(DISTINCT user_id) FROM access_logs
        WHERE created_at >= datetime('now', '+9 hours', '-7 days')
          AND user_id != 'admin'
    """).fetchone()[0]

    month_active = conn.execute("""
        SELECT COUNT(DISTINCT user_id) FROM access_logs
        WHERE created_at >= datetime('now', '+9 hours', '-30 days')
          AND user_id != 'admin'
    """).fetchone()[0]

    # 일별 활동 추이 (최근 30일)
    daily_activity = conn.execute("""
        SELECT DATE(created_at) as date,
               COUNT(DISTINCT user_id) as active_users,
               SUM(CASE WHEN action = 'page_view' AND page = '/simulation' THEN 1 ELSE 0 END) as roleplay_views,
               SUM(CASE WHEN action = 'page_view' AND page = '/quiz' THEN 1 ELSE 0 END) as quiz_views
        FROM access_logs
        WHERE created_at >= datetime('now', '+9 hours', '-30 days')
          AND user_id != 'admin'
        GROUP BY DATE(created_at)
        ORDER BY date
    """).fetchall()

    return {
        "total_users": total_users,
        "total_roleplay": total_roleplay,
        "total_quiz": total_quiz,
        "week_active": week_active,
        "month_active": month_active,
        "daily_activity": [dict(r) for r in daily_activity],
    }


def get_all_members_summary() -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT
            u.id, u.name, u.department, u.position,
            COALESCE(rp.cnt, 0) as roleplay_count,
            rp.avg_grade,
            COALESCE(qz.cnt, 0) as quiz_count,
            qz.accuracy,
            COALESCE(al.last_active, u.created_at) as last_active
        FROM users u
        LEFT JOIN (
            SELECT user_id,
                   COUNT(*) as cnt,
                   GROUP_CONCAT(overall_grade) as grades,
                   ROUND(AVG(CASE overall_grade
                       WHEN 'A' THEN 4 WHEN 'B' THEN 3
                       WHEN 'C' THEN 2 WHEN 'D' THEN 1 ELSE NULL END), 1) as avg_grade_num,
                   CASE
                       WHEN ROUND(AVG(CASE overall_grade
                           WHEN 'A' THEN 4 WHEN 'B' THEN 3
                           WHEN 'C' THEN 2 WHEN 'D' THEN 1 ELSE NULL END), 1) >= 3.5 THEN 'A'
                       WHEN ROUND(AVG(CASE overall_grade
                           WHEN 'A' THEN 4 WHEN 'B' THEN 3
                           WHEN 'C' THEN 2 WHEN 'D' THEN 1 ELSE NULL END), 1) >= 2.5 THEN 'B'
                       WHEN ROUND(AVG(CASE overall_grade
                           WHEN 'A' THEN 4 WHEN 'B' THEN 3
                           WHEN 'C' THEN 2 WHEN 'D' THEN 1 ELSE NULL END), 1) >= 1.5 THEN 'C'
                       ELSE 'D'
                   END as avg_grade
            FROM roleplay_sessions GROUP BY user_id
        ) rp ON u.id = rp.user_id
        LEFT JOIN (
            SELECT user_id,
                   COUNT(*) as cnt,
                   ROUND(100.0 * SUM(is_correct) / COUNT(*), 1) as accuracy
            FROM quiz_records GROUP BY user_id
        ) qz ON u.id = qz.user_id
        LEFT JOIN (
            SELECT user_id, MAX(created_at) as last_active
            FROM access_logs GROUP BY user_id
        ) al ON u.id = al.user_id
        WHERE u.role = 'user'
        ORDER BY al.last_active DESC
    """).fetchall()
    return [_with_kst(dict(r)) for r in rows]


def get_member_detail(user_id: str) -> dict:
    conn = _connect()
    user = _with_kst(dict(conn.execute("SELECT id, name, department, position, created_at FROM users WHERE id = ?", (user_id,)).fetchone()))

    # 롤플레이 세션 (전체 대화 포함)
    rp_rows = conn.execute(
        """SELECT id, scenario_key, scenario_title, persona_level, overall_grade,
                  conversation, feedback, turn_count, started_at, ended_at, duration_seconds
           FROM roleplay_sessions WHERE user_id = ? ORDER BY ended_at DESC""",
        (user_id,),
    ).fetchall()
    sessions = []
    for r in rp_rows:
        d = dict(r)
        d["conversation"] = json.loads(d["conversation"]) if d["conversation"] else []
        d["feedback"] = json.loads(d["feedback"]) if d["feedback"] else None
        sessions.append(_with_kst(d))

    # 퀴즈 기록
    qz_rows = conn.execute(
        """SELECT id, category, difficulty, question, user_answer, correct_answer, is_correct, answered_at
           FROM quiz_records WHERE user_id = ? ORDER BY answered_at DESC""",
        (user_id,),
    ).fetchall()

    return {
        "user": user,
        "roleplay_sessions": sessions,
        "quiz_records": [_with_kst(dict(r)) for r in qz_rows],
    }


def get_access_logs(user_id: str | None = None, start_date: str | None = None, end_date: str | None = None, page: str | None = None, limit: int = 500) -> list[dict]:
    conn = _connect()
    query = """
        SELECT al.id, al.user_id, u.name, al.action, al.page, al.ip_address, al.created_at
        FROM access_logs al
        JOIN users u ON al.user_id = u.id
        WHERE 1=1
    """
    params = []
    if user_id:
        query += " AND al.user_id = ?"
        params.append(user_id)
    if start_date:
        query += " AND al.created_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND al.created_at <= ?"
        params.append(end_date)
    if page:
        query += " AND al.page = ?"
        params.append(page)
    query += " ORDER BY al.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [_with_kst(dict(r)) for r in rows]


def get_improvements_ranking(limit: int = 10) -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT feedback FROM roleplay_sessions WHERE feedback IS NOT NULL").fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        fb = json.loads(row["feedback"]) if row["feedback"] else {}
        for item in fb.get("improvements", []):
            item_clean = item.strip()
            if item_clean:
                counts[item_clean] = counts.get(item_clean, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"improvement": k, "count": v} for k, v in ranked]
