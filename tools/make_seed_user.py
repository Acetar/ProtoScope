"""种子账号口令哈希生成：与 server/app/auth.py 完全同一算法。

用法：
    cd server && python ../tools/make_seed_user.py demo1234
把输出贴进 deploy/db/init/03_seed.sql。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app import auth  # noqa: E402


def main() -> None:
    pwd = sys.argv[1] if len(sys.argv) > 1 else "demo1234"
    h = auth.hash_password(pwd)
    assert auth.verify_password(pwd, h), "生成后自检失败"
    print(f"password : {pwd}")
    print(f"hash     : {h}")
    print("SQL      : INSERT INTO users (email, password_hash) VALUES "
          f"('demo@lab.test', '{h}') ON CONFLICT (email) DO NOTHING;")


if __name__ == "__main__":
    main()
