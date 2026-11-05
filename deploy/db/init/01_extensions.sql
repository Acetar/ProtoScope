-- 01 扩展
-- vector : 知识库向量检索（设计文档 5.2 knowledge_chunks），需要 pgvector 镜像
-- pg_trgm: 字段值模糊搜索（"找出所有含 academy 的报文"），官方镜像自带
--
-- 两个都做成"有则建、无则跳过"：换镜像（含 / 不含 pgvector）都能直接起，
-- 不至于因为一个扩展让整个 initdb 失败、后面建表脚本一个都不执行。
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
    RAISE NOTICE 'pgvector ready';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector unavailable (%) — prototype does not need it yet', SQLERRM;
END $$;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_trgm unavailable (%) — fuzzy search falls back to ILIKE', SQLERRM;
END $$;
