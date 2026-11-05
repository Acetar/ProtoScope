"""存储层：用户 + 我的动画 + 抓包。

一套业务代码，两种驱动：
- 默认 SQLite（`server/data/app.db`）：零依赖，答辩现场拷一个文件就能跑；
- 设置 `DATABASE_URL=postgresql://...` 时切到 PostgreSQL（`deploy/docker-compose.yml` 起容器）。

切换只在 `connect()` 一层：业务函数不关心底下是什么库，只用到
`execute / fetchone / fetchall / rowcount` 这几个接口，行对象都支持 `row["col"]`。
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"

DSN = os.getenv("DATABASE_URL", "").strip()
USE_PG = DSN.startswith(("postgres://", "postgresql://"))

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TEXT NOT NULL,
    last_login_at TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT,
    llm_base_url  TEXT,
    llm_api_key   TEXT,
    llm_model     TEXT
);

CREATE TABLE IF NOT EXISTS animations (
    id              TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point TEXT NOT NULL,
    title           TEXT NOT NULL,
    duration_sec    REAL NOT NULL,
    props_json      TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_animations_user ON animations(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS captures (
    id            TEXT PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    size          INTEGER NOT NULL,
    packet_count  INTEGER NOT NULL,
    session_count INTEGER NOT NULL,
    data_json     TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_captures_user ON captures(user_id, created_at DESC);
"""

# PostgreSQL：类型与设计文档 5.2 对齐（BIGSERIAL / TIMESTAMPTZ / JSONB 留给正式版）
SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(16) NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    failed_attempts SMALLINT NOT NULL DEFAULT 0,
    locked_until  TIMESTAMPTZ,
    llm_base_url  TEXT,
    llm_api_key   TEXT,
    llm_model     TEXT
);

CREATE TABLE IF NOT EXISTS animations (
    id              VARCHAR(16) PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point VARCHAR(64) NOT NULL,
    title           TEXT NOT NULL,
    duration_sec    REAL NOT NULL,
    props_json      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_animations_user ON animations(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS captures (
    id            VARCHAR(16) PRIMARY KEY,
    user_id       BIGINT REFERENCES users(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    size          INTEGER NOT NULL,
    packet_count  INTEGER NOT NULL,
    session_count INTEGER NOT NULL,
    data_json     JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_captures_user ON captures(user_id, created_at DESC);
"""


# 会话与消息（AI 教师的多会话记录）单独成块：老库升级时也会被 CREATE TABLE IF NOT EXISTS 补上
SCHEMA_CHAT_SQLITE = """
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    topic_id   TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'text',
    content         TEXT NOT NULL DEFAULT '',
    payload_json    TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""

SCHEMA_CHAT_PG = """
CREATE TABLE IF NOT EXISTS conversations (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(120) NOT NULL,
    topic_id   VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    kind            VARCHAR(24) NOT NULL DEFAULT 'text',
    content         TEXT NOT NULL DEFAULT '',
    payload_json    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


# 老库补列：(列名, 类型)。两种驱动都能 ALTER 加列，但 SQLite 不支持 IF NOT EXISTS
_TS_TYPE = "TIMESTAMPTZ" if USE_PG else "TEXT"

NEW_USER_COLUMNS = [
    ("role", "VARCHAR(16) NOT NULL DEFAULT 'user'" if USE_PG else "TEXT NOT NULL DEFAULT 'user'"),
    ("last_login_at", _TS_TYPE),
    ("failed_attempts", "SMALLINT NOT NULL DEFAULT 0" if USE_PG else "INTEGER NOT NULL DEFAULT 0"),
    ("locked_until", _TS_TYPE),
    ("llm_base_url", "TEXT"),
    ("llm_api_key", "TEXT"),
    ("llm_model", "TEXT"),
]


class _Cur:
    """把 sqlite3.Cursor 与 psycopg2.cursor 的差异收在一起。"""

    __slots__ = ("_raw", "_pg")

    def __init__(self, raw: Any, pg: bool) -> None:
        self._raw = raw
        self._pg = pg

    def _row(self, row: Any) -> Any:
        if row is None:
            return None
        # psycopg2 的 RealDictRow 已是 dict；sqlite3.Row 需要转换
        return dict(row) if self._pg else row

    def fetchone(self) -> Any:
        return self._row(self._raw.fetchone())

    def fetchall(self) -> list[Any]:
        return [self._row(r) for r in self._raw.fetchall()]

    def __iter__(self):
        # 允许 `for row in conn.execute(...)`（init() 里读列名用）
        return iter(self.fetchall())

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    @property
    def lastrowid(self) -> Any:
        # psycopg2 没有 lastrowid，调用方在 PG 下改用 RETURNING id（见 _insert_id）
        return self._raw.lastrowid


class _Conn:
    __slots__ = ("_raw", "_pg")

    def __init__(self, raw: Any, pg: bool) -> None:
        self._raw = raw
        self._pg = pg

    def execute(self, sql: str, params: tuple | None = None) -> _Cur:
        if self._pg:
            sql = sql.replace("?", "%s")
            cur = self._raw.cursor()
            cur.execute(sql, params) if params else cur.execute(sql)
            return _Cur(cur, True)
        cur = self._raw.execute(sql, params) if params else self._raw.execute(sql)
        return _Cur(cur, False)

    def executescript(self, script: str) -> None:
        if self._pg:
            cur = self._raw.cursor()
            cur.execute(script)
            return
        self._raw.executescript(script)


def _insert_id(conn: _Conn, sql: str, params: tuple) -> Any:
    """INSERT 后拿自增主键：SQLite 用 lastrowid，PG 用 RETURNING id。"""
    cur = conn.execute(sql + " RETURNING id" if USE_PG else sql, params)
    return cur.fetchone()["id"] if USE_PG else cur.lastrowid


def _now() -> Any:
    # PG 的 created_at 是 TIMESTAMPTZ，传 datetime 让它自己转；SQLite 存 ISO 文本
    return datetime.now(timezone.utc) if USE_PG else datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[_Conn]:
    if USE_PG:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        raw = psycopg2.connect(DSN, cursor_factory=RealDictCursor)
        conn = _Conn(raw, True)
        try:
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(DB_PATH, timeout=10)
    raw.row_factory = sqlite3.Row
    conn = _Conn(raw, False)
    try:
        yield conn
        raw.commit()
    finally:
        raw.close()


def init() -> None:
    with connect() as conn:
        if USE_PG:
            conn.executescript(SCHEMA_PG)
            conn.executescript(SCHEMA_CHAT_PG)
            cols = {
                row["column_name"]
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
                ).fetchall()
            }
            # PG 支持 ADD COLUMN IF NOT EXISTS，但显式判断更直观，也便于老库平滑
            for name, ddl_type in NEW_USER_COLUMNS:
                if name not in cols:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl_type}")
            return

        conn.executescript(SCHEMA_SQLITE)
        conn.executescript(SCHEMA_CHAT_SQLITE)
        # 轻量迁移：老库没有这几列时补上（SQLite 不支持 IF NOT EXISTS 加列）
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        for name, ddl_type in NEW_USER_COLUMNS:
            if name not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl_type}")


def backend() -> str:
    """给 /api/health 用：让人一眼看出现在连的是哪种库。"""
    return "postgresql" if USE_PG else "sqlite"


# ---------- LLM 设置（BYOK：用户自带 key） ----------

def get_llm_settings(user_id: int) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT llm_base_url, llm_api_key, llm_model FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else {}


def save_llm_settings(
    user_id: int,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
) -> dict:
    """api_key 传空字符串表示"保留原值"，避免前端拿到掩码后又把它覆盖回去。"""
    current = get_llm_settings(user_id)
    new_key = current.get("llm_api_key") if not api_key else api_key
    with connect() as conn:
        conn.execute(
            "UPDATE users SET llm_base_url = ?, llm_api_key = ?, llm_model = ? WHERE id = ?",
            (base_url or None, new_key or None, model or None, user_id),
        )
    return get_llm_settings(user_id)


def mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}{'*' * 6}{key[-4:]}"


# ---------- users ----------

def create_user(email: str, password_hash: str, role: str = "user") -> dict:
    email = email.lower().strip()
    with connect() as conn:
        new_id = _insert_id(
            conn,
            "INSERT INTO users(email, password_hash, role, created_at) VALUES (?,?,?,?)",
            (email, password_hash, role, _now()),
        )
    return {"id": new_id, "email": email, "role": role}


def find_user_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def find_user_by_id(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def note_login_failure(user_id: int, max_attempts: int = 5, lock_minutes: int = 15) -> dict:
    """记一次失败；达到阈值就锁定。返回 {attempts, lockedUntil}。"""
    from datetime import timedelta

    with connect() as conn:
        row = conn.execute(
            "SELECT failed_attempts FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        attempts = int(row["failed_attempts"] or 0) + 1 if row else 1
        locked_until = None
        if attempts >= max_attempts:
            until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
            locked_until = until if USE_PG else until.isoformat(timespec="seconds")
        conn.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            (attempts, locked_until, user_id),
        )
    return {"attempts": attempts, "lockedUntil": locked_until}


def note_login_success(user_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ?"
            " WHERE id = ?",
            (_now(), user_id),
        )


# ---------- animations ----------

def save_animation(
    user_id: int,
    props: dict,
    meta: dict | None = None,
) -> dict:
    item_id = uuid.uuid4().hex[:12]
    row = {
        "id": item_id,
        "user_id": user_id,
        "knowledge_point": props.get("knowledgePoint", "custom"),
        "title": props.get("title", "未命名动画"),
        "duration_sec": round(props.get("totalFrames", 0) / props.get("fps", 30), 2),
        "props_json": json.dumps(props, ensure_ascii=False),
        "created_at": _now(),
    }
    with connect() as conn:
        conn.execute(
            "INSERT INTO animations(id, user_id, knowledge_point, title, duration_sec,"
            " props_json, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                row["id"],
                row["user_id"],
                row["knowledge_point"],
                row["title"],
                row["duration_sec"],
                row["props_json"],
                row["created_at"],
            ),
        )
    return row


def list_animations(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, knowledge_point, title, duration_sec, created_at"
            " FROM animations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_animation(user_id: int, item_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM animations WHERE id = ? AND user_id = ?", (item_id, user_id)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        raw = data.pop("props_json")
        # SQLite 存 TEXT（字符串），PostgreSQL 的 JSONB 由驱动直接解析成 dict
        data["props"] = json.loads(raw) if isinstance(raw, str) else raw
        return data


def delete_animation(user_id: int, item_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM animations WHERE id = ? AND user_id = ?", (item_id, user_id)
        )
        return cur.rowcount > 0


def stats() -> dict[str, Any]:
    with connect() as conn:
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        anims = conn.execute("SELECT COUNT(*) c FROM animations").fetchone()["c"]
        caps = conn.execute("SELECT COUNT(*) c FROM captures").fetchone()["c"]
    return {"users": users, "animations": anims, "captures": caps, "backend": backend()}


def list_users() -> list[dict[str, Any]]:
    """管理员看用户列表：只给身份与状态，绝不带 password_hash / llm_api_key。"""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, email, role, created_at, last_login_at, failed_attempts, locked_until,"
            " CASE WHEN llm_api_key IS NULL OR llm_api_key = '' THEN 0 ELSE 1 END AS has_key"
            " FROM users ORDER BY id ASC"
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["has_key"] = bool(item.get("has_key"))
        item["locked"] = item.pop("locked_until", None)
        out.append(item)
    return out


def set_user_role(user_id: int, role: str) -> bool:
    with connect() as conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return cur.rowcount > 0



# ---------------------------------------------------------------- captures

def save_capture(
    user_id: int | None,
    filename: str,
    size: int,
    packet_count: int,
    session_count: int,
    parsed: dict[str, Any],
) -> str:
    cap_id = uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            "INSERT INTO captures (id, user_id, filename, size, packet_count,"
            " session_count, data_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (cap_id, user_id, filename, size, packet_count, session_count,
             json.dumps(parsed, ensure_ascii=False), _now()),
        )
    return cap_id


def list_captures(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, size, packet_count, session_count, created_at"
            " FROM captures WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_capture(user_id: int, cap_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM captures WHERE id = ? AND user_id = ?", (cap_id, user_id)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        raw = data.pop("data_json")
        data["parsed"] = json.loads(raw) if isinstance(raw, str) else raw
        return data


def delete_capture(user_id: int, cap_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM captures WHERE id = ? AND user_id = ?", (cap_id, user_id)
        )
        return cur.rowcount > 0


# ---------- 会话与消息（AI 教师） ----------
# 一个会话 = 一段连续的教学对话；消息按 id 递增即为时间序。
# 前端左侧列表只需要 title / 时间 / 最后一条内容摘要，所以 list 里带 message_count 与 last_snippet。

def _conv_out(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "title": row.get("title") or "新对话",
        "topicId": row.get("topic_id") or "",
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "messageCount": int(row.get("message_count") or 0),
        "lastSnippet": row.get("last_snippet") or "",
    }


def list_conversations(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            " (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,"
            " (SELECT COALESCE(m2.content, m2.kind) FROM messages m2"
            "   WHERE m2.conversation_id = c.id ORDER BY m2.id DESC LIMIT 1) AS last_snippet"
            " FROM conversations c WHERE c.user_id = ?"
            " ORDER BY c.updated_at DESC, c.id DESC",
            (user_id,),
        ).fetchall()
        return [_conv_out(dict(r)) for r in rows]


def create_conversation(user_id: int, title: str = "新对话", topic_id: str | None = None) -> dict:
    now = _now()
    with connect() as conn:
        conv_id = _insert_id(
            conn,
            "INSERT INTO conversations (user_id, title, topic_id, created_at, updated_at)"
            " VALUES (?,?,?,?,?)",
            (user_id, title or "新对话", topic_id or None, now, now),
        )
        row = conn.execute(
            "SELECT c.*, 0 AS message_count, '' AS last_snippet"
            " FROM conversations c WHERE c.id = ?",
            (conv_id,),
        ).fetchone()
        return _conv_out(dict(row))


def get_conversation(user_id: int, conv_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT c.*, "
            " (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,"
            " '' AS last_snippet"
            " FROM conversations c WHERE c.id = ? AND c.user_id = ?",
            (conv_id, user_id),
        ).fetchone()
        return _conv_out(dict(row)) if row else None


def rename_conversation(user_id: int, conv_id: int, title: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title.strip()[:120], _now(), conv_id, user_id),
        )
        return cur.rowcount > 0


def touch_conversation(conv_id: int, title: str | None = None) -> None:
    """每条新消息后调用：把会话顶到列表最前；标题仍是默认值时顺手改成首句问题。"""
    with connect() as conn:
        if title:
            conn.execute(
                "UPDATE conversations SET updated_at = ?, title = ? WHERE id = ?",
                (_now(), title.strip()[:120], conv_id),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conv_id)
            )


def delete_conversation(user_id: int, conv_id: int) -> bool:
    with connect() as conn:
        # messages 靠外键级联；显式删一次更保险（SQLite 默认没开外键约束）
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)
        )
        return cur.rowcount > 0


def _msg_out(row: dict) -> dict:
    data = dict(row)
    raw = data.pop("payload_json", None)
    data["payload"] = json.loads(raw) if isinstance(raw, str) else raw
    data["conversationId"] = int(data.pop("conversation_id"))
    data["kind"] = data.get("kind") or "text"
    return data


def list_messages(user_id: int, conv_id: int) -> list[dict]:
    with connect() as conn:
        owns = conn.execute(
            "SELECT 1 AS ok FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)
        ).fetchone()
        if not owns:
            return []
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)
        ).fetchall()
        return [_msg_out(dict(r)) for r in rows]


def add_message(
    conv_id: int,
    role: str,
    content: str = "",
    kind: str = "text",
    payload: dict | None = None,
) -> dict:
    now = _now()
    with connect() as conn:
        msg_id = _insert_id(
            conn,
            "INSERT INTO messages (conversation_id, role, kind, content, payload_json, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (conv_id, role, kind, content or "", json.dumps(payload, ensure_ascii=False) if payload else None, now),
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return _msg_out(dict(row))
