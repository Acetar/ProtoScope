-- 03 种子数据：演示账号（口令 demo1234）
-- 哈希由 tools/make_seed_user.py 用与 server/app/auth.py 相同的算法（PBKDF2-SHA256，20 万次）生成，
-- 格式为 "salt_hex$dk_hex"；换口令请重新生成，别手改。
INSERT INTO users (email, password_hash, role)
VALUES ('demo@lab.test', '920f002e6ae4e019b313e3c96d15452c$97f2cbe66316f7b076dde26da538ad8db0087b3c31898aac206771bbbb277589', 'admin')
ON CONFLICT (email) DO NOTHING;
