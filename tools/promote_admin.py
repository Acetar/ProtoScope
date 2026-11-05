"""把某个邮箱对应的账号提升为管理员（或降回普通用户）。

用法：
    python tools/promote_admin.py 1249546896@qq.com          # 提升为 admin
    python tools/promote_admin.py 1249546896@qq.com user     # 降回 user
    python tools/promote_admin.py --list                     # 列出所有账号与角色

用途：答辩现场换机 / 忘记管理员口令时，不依赖 psql 也能把自己变成管理员。
连接哪个库由环境变量 DATABASE_URL 决定，不设则用 server/data/app.db。
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server"))

from app import db  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    db.init()

    if not args or args[0] == "--list":
        with db.connect() as conn:
            rows = conn.execute("SELECT id, email, role FROM users ORDER BY id").fetchall()
        print(f"backend = {db.backend()}")
        for r in rows:
            print(f"  {r['id']:>4}  {r['email']:<32} {r['role']}")
        return 0

    email = args[0].lower().strip()
    role = args[1] if len(args) > 1 else "admin"
    if role not in ("user", "admin"):
        print("role 只能是 user 或 admin")
        return 2

    user = db.find_user_by_email(email)
    if not user:
        print(f"没有这个账号：{email}（先在前端注册一次）")
        return 1
    db.set_user_role(int(user["id"]), role)
    print(f"已把 {email}（id={user['id']}）设为 {role}；重新登录后生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
