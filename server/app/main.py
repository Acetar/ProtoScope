"""FastAPI 入口：认证 / 设置 / 生成 / 目录 / 渲染 / 静态产物。

LLM 采用 BYOK（用户自带 key）：优先用当前用户在设置里填的 DeepSeek 配置，
没有则回退到环境变量，两者都没有就走规则库。
"""
from __future__ import annotations

import os
import time

import re
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import auth, catalog, db, from_capture, llm, pcap, planner, render, tutor
from .models import AnimationProps, GenerateRequest, KnowledgePoint, RenderJob

app = FastAPI(title="NetProtocol Motion API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init()


# ---------- 内置管理员 ----------
# 每次启动都保证存在一个管理员账号：SQLite 与 Docker PG 都生效
# （PG 首次建库时 initdb 也会写一个，但换库、清库、换机之后这里兜底）。
# 想换账号/口令就设环境变量 ADMIN_EMAIL / ADMIN_PASSWORD。
ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "admin@lab.test").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "admin1234"


def ensure_builtin_admin() -> None:
    user = db.find_user_by_email(ADMIN_EMAIL)
    if user is None:
        db.create_user(ADMIN_EMAIL, auth.hash_password(ADMIN_PASSWORD), role="admin")
        print(f"[init] created builtin admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        return
    if (user.get("role") or "") != "admin":
        db.set_user_role(int(user["id"]), "admin")
        print(f"[init] promoted existing account to admin: {ADMIN_EMAIL}")
        return
    print(f"[init] builtin admin ready: {ADMIN_EMAIL}")


ensure_builtin_admin()
render.OUT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(render.OUT)), name="media")


# ---------- 用户设置 → LLM 配置 ----------

def _env_config() -> llm.LLMConfig | None:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        return None
    return llm.LLMConfig(
        base_url=os.environ.get("LLM_BASE_URL", llm.DEEPSEEK_BASE),
        api_key=key,
        model=os.environ.get("LLM_MODEL", llm.DEEPSEEK_MODEL),
    )


def _config_for(user: dict | None) -> llm.LLMConfig | None:
    if user:
        s = db.get_llm_settings(user["id"])
        if s.get("llm_api_key"):
            return llm.LLMConfig(
                base_url=s.get("llm_base_url") or llm.DEEPSEEK_BASE,
                api_key=s["llm_api_key"],
                model=s.get("llm_model") or llm.DEEPSEEK_MODEL,
            )
    return _env_config()


# ---------- 基础 ----------

@app.get("/api/health")
def health() -> dict:
    # db 字段让"现在连的是 SQLite 还是 Docker 里的 PG"一眼可见，演示时有用
    return {"ok": True, "db": db.backend(), "llmEnv": bool(_env_config())}


@app.get("/api/knowledge-points", response_model=list[KnowledgePoint])
def knowledge_points() -> list[dict]:
    return catalog.summary()


# ---------- 认证 ----------

def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user.get("role") or "user",
        "createdAt": str(user.get("created_at") or ""),
    }

LOCK_MINUTES = 15
MAX_ATTEMPTS = 5


def _as_dt(value) -> datetime | None:
    """时间值统一成带时区的 datetime。

    三种来源：SQLite 的 ISO 字符串、psycopg2 的 datetime、
    以及 PG 把 TIMESTAMPTZ 隐式转成文本时的 '2026-11-05 15:28:20.17+08'
    （带空格分隔与两位时区，Python 3.10 的 fromisoformat 不认，得先规范化）。
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace(" ", "T")
    if re.search(r"[+-]\d{2}$", text):          # +08 → +08:00
        text += ":00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _locked_now(user: dict):
    until = _as_dt(user.get("locked_until"))
    if until and until > datetime.now(timezone.utc):
        return until
    return None


def _minutes_left(until: datetime) -> int:
    delta = (until - datetime.now(timezone.utc)).total_seconds()
    return max(1, int(delta // 60) + (1 if delta % 60 else 0))


@app.post("/api/auth/register", status_code=201)
def register(payload: dict) -> dict:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if db.find_user_by_email(email):
        raise HTTPException(status_code=409, detail="这个邮箱已经注册过了")

    created = db.create_user(email, auth.hash_password(password))
    # 回查一次，把 created_at / role 等默认值一并返回给前端
    user = db.find_user_by_id(created["id"]) or created
    return {"token": auth.make_token(user["id"], user["email"]), "user": _public_user(user)}


@app.post("/api/auth/login")
def login(payload: dict) -> dict:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = db.find_user_by_email(email)

    # 统一文案：不区分"用户不存在"和"密码错"，避免账号枚举
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码不对")

    locked_until = _locked_now(user)
    if locked_until:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "TOO_MANY_ATTEMPTS",
                "message": f"尝试次数过多，请 {_minutes_left(locked_until)} 分钟后再试",
            },
        )

    if not auth.verify_password(password, user["password_hash"]):
        state = db.note_login_failure(user["id"])
        if state.get("lockedUntil"):
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "TOO_MANY_ATTEMPTS",
                    "message": f"连续失败 {state['attempts']} 次，账号已锁定 {LOCK_MINUTES} 分钟",
                },
            )
        raise HTTPException(status_code=401, detail="邮箱或密码不对")

    db.note_login_success(user["id"])
    return {"token": auth.make_token(user["id"], user["email"]), "user": _public_user(user)}


@app.get("/api/auth/me")
def me(user: dict | None = Depends(auth.optional_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return _public_user(user)


# ---------- 设置（BYOK） ----------

@app.get("/api/settings")
def get_settings(user: dict = Depends(auth.require_user)) -> dict:
    s = db.get_llm_settings(user["id"])
    return {
        "baseUrl": s.get("llm_base_url") or "",
        "model": s.get("llm_model") or "",
        "hasKey": bool(s.get("llm_api_key")),
        "maskedKey": db.mask_key(s.get("llm_api_key")),
        "defaults": {"baseUrl": llm.DEEPSEEK_BASE, "model": llm.DEEPSEEK_MODEL},
    }


@app.put("/api/settings")
def put_settings(payload: dict, user: dict = Depends(auth.require_user)) -> dict:
    base_url = (payload.get("baseUrl") or "").strip()
    model = (payload.get("model") or "").strip()
    api_key = (payload.get("apiKey") or "").strip()
    if base_url and not base_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Base URL 需要以 http(s):// 开头")
    db.save_llm_settings(user["id"], base_url, api_key, model)
    return get_settings(user)


# ---------- 生成 ----------

@app.post("/api/generate")
def generate(req: GenerateRequest, user: dict | None = Depends(auth.optional_user)) -> dict:
    try:
        result = planner.generate(req, _config_for(user))
    except planner.NoMatchError as exc:
        # 400 而不是 422：这不是"请求格式不对"，而是"当前配置下这个需求做不了"，
        # 前端要根据 message + suggestions 给出可操作提示
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "suggestions": exc.suggestions},
        ) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    payload = planner.to_payload(result)

    # 登录用户顺手存一份，未登录只返回不落库
    if user:
        try:
            anim = db.save_animation(user["id"], payload["props"], payload["meta"])
            payload["meta"]["animationId"] = anim["id"]
        except Exception:  # 存库失败不该让生成失败
            pass
    return payload


# ---------- 我的动画 ----------

@app.get("/api/animations")
def list_animations(user: dict = Depends(auth.require_user)) -> list[dict]:
    return db.list_animations(user["id"])


@app.post("/api/animations", status_code=201)
def create_animation(payload: dict, user: dict = Depends(auth.require_user)) -> dict:
    props = payload.get("props") or payload
    try:
        AnimationProps(**props)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return db.save_animation(user["id"], props, payload.get("meta"))


@app.get("/api/animations/{anim_id}")
def get_animation(anim_id: str, user: dict = Depends(auth.require_user)) -> dict:
    anim = db.get_animation(user["id"], anim_id)
    if not anim:
        raise HTTPException(status_code=404, detail="动画不存在")
    return anim


@app.delete("/api/animations/{anim_id}")
def remove_animation(anim_id: str, user: dict = Depends(auth.require_user)) -> dict:
    if not db.delete_animation(user["id"], anim_id):
        raise HTTPException(status_code=404, detail="动画不存在")
    return {"ok": True}


# ---------- 抓包 ----------

@app.post("/api/captures")
async def upload_capture(
    file: UploadFile = File(...),
    user: dict | None = Depends(auth.optional_user),
) -> dict:
    """上传 pcap/pcapng，返回解析结果；登录用户额外落库，便于以后回看。"""
    data = await file.read()
    try:
        parsed = pcap.parse_capture(data, file.filename or "capture.pcap")
    except pcap.CaptureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    capture_id = None
    if user:
        try:
            capture_id = db.save_capture(
                user["id"], parsed["filename"], parsed["size"],
                parsed["packetCount"], parsed["sessionCount"], parsed,
            )
        except Exception:  # noqa: BLE001  存库失败不该让上传失败
            capture_id = None

    return {"captureId": capture_id, "parsed": parsed}


@app.get("/api/captures")
def list_captures(user: dict = Depends(auth.require_user)) -> list[dict]:
    return db.list_captures(user["id"])


@app.get("/api/captures/{cap_id}")
def get_capture(cap_id: str, user: dict = Depends(auth.require_user)) -> dict:
    cap = db.get_capture(user["id"], cap_id)
    if not cap:
        raise HTTPException(status_code=404, detail="抓包记录不存在")
    return cap


@app.delete("/api/captures/{cap_id}")
def remove_capture(cap_id: str, user: dict = Depends(auth.require_user)) -> dict:
    if not db.delete_capture(user["id"], cap_id):
        raise HTTPException(status_code=404, detail="抓包记录不存在")
    return {"ok": True}


@app.post("/api/captures/animate")
def animate_capture(payload: dict) -> dict:
    """把一个会话翻译成动画剧本。前端把选中的会话连同报文一起发上来。"""
    started = time.perf_counter()
    session = payload.get("session") or {}
    packets = payload.get("packets") or []
    duration = float(payload.get("durationSec") or 12)
    try:
        raw = from_capture.build_from_capture(session, packets, duration)
        props = planner._dump(AnimationProps(**raw))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "props": props,
        "meta": {
            "source": "capture",
            "knowledgePoint": props["knowledgePoint"],
            "durationSec": round(props["totalFrames"] / props["fps"], 1),
            "totalFrames": props["totalFrames"],
            "elapsedMs": round((time.perf_counter() - started) * 1000),
            "notes": ["由真实抓包翻译而来：报文条数与时间顺序与原始文件一致。"],
        },
    }


# ---------- AI 教师 ----------

@app.post("/api/tutor/ask")
def tutor_ask(payload: dict, user: dict | None = Depends(auth.optional_user)):
    """把「当前知识点 + 若干报文」作为上下文，流式回答学生的问题。

    走 SSE：text/event-stream，每个事件是一小段文本。
    没有可用 key 时仍返回 200，只是内容是规则兜底——前端因此不需要特判降级。
    """
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="问题太长了，控制在 500 字以内")

    topic_id = payload.get("topic") or ""
    topic = next((t for t in catalog.CATALOG if t["id"] == topic_id), None)
    scenes = tutor.scenes_from_props(payload.get("props") or {}) if payload.get("props") else None
    ctx = tutor.build_context(topic, scenes)
    history = payload.get("history") or []
    cfg = _config_for(user)

    def gen():
        try:
            for piece in tutor.answer(cfg, ctx, question, history):
                # SSE 要求每条消息里不能有裸换行，折算成 \n 转义
                data = piece.replace("\r", "")
                for line in data.split("\n"):
                    yield f"event: token\ndata: {line}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001  流已开始，只能把错误写进流里
            yield f"event: error\ndata: {str(exc)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ---------- 管理员 ----------

def require_admin(user: dict = Depends(auth.require_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@app.get("/api/admin/users")
def admin_users(user: dict = Depends(require_admin)) -> list[dict]:
    return db.list_users()


@app.post("/api/admin/users/{user_id}/role")
def admin_set_role(user_id: int, payload: dict, admin: dict = Depends(require_admin)) -> dict:
    role = payload.get("role")
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role 只能是 user 或 admin")
    if user_id == admin["id"]:
        # 防止唯一的管理员把自己降级，把自己锁在门外
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    if not db.set_user_role(user_id, role):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True}


@app.get("/api/admin/stats")
def admin_stats(user: dict = Depends(require_admin)) -> dict:
    return db.stats()


# ---------- 渲染 ----------

@app.post("/api/renders", response_model=RenderJob, status_code=202)
def create_render(payload: dict) -> dict:
    try:
        props = planner._dump(AnimationProps(**(payload.get("props") or payload)))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return render.create(props)


@app.get("/api/renders/{job_id}", response_model=RenderJob)
def get_render(job_id: str) -> dict:
    job = render.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return job
