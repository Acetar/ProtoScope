# 大模型驱动的网络协议交互可视化学习平台

把"看不见的协议交互"变成**可生成、可播放、可导出**的学习对象：
选一个知识点（或用一句话描述需求）→ 规则库 / DeepSeek 编排出一份动画剧本 →
浏览器里用 Remotion Player 即时预览 → 一键导出 1080p MP4。

技术栈：**Vue 3 + Vite + FastAPI + PostgreSQL（Docker）/ SQLite + Remotion**（大模型走 OpenAI 兼容协议，
采用 BYOK：key 由每个用户自己填，服务端不存全局密钥）。

## 产品形态（定稿）

只有两个角色，**没有教师端**：

```
未登录 ──► 落地页（项目目的 / 功能 / 原理，右上角登录）；功能一律不展示
              │ 注册 / 登录
              ▼
        用户端 ──┬── A. 协议动画演示 + 知识汇总
                 └── B. AI 交流模块
                          ├── B1. AI 扮演计算机网络教师：讲课 + 答疑
                          └── B2. 按需求生成 Remotion 科普动画并展示
        管理员端 ── 用户列表 / 角色管理 / 用量总览
```

A 与 B2 是同一套渲染器、同一份 props 契约，只是剧本来源不同（规则库 / 大模型）；
B1 复用 A 的结构化事实（当前知识点的报文与字段）作为上下文，不凭空编数字。

## 当前进度

| 阶段 | 状态 |
| --- | --- |
| 设计文档 v1.0（含 4.6 AI 动效科普） | ✅ 已完成（[docs/设计文档.md](docs/设计文档.md)） |
| Remotion 渲染工程（Composition + props 契约） | ✅ 已完成（[renderer/](renderer/README.md)） |
| 知识库六主题规则编排 | ✅ 已完成（TCP 握手 / 四次挥手 / TLS / HTTP / ARP / DNS） |
| 后端 API（认证 / 设置 / 生成 / 作品 / 渲染） | ✅ 已完成（[server/](server/app/main.py)） |
| 前端工作台（目录 / 预览 / 导出） | ✅ 已完成（[web/](web/src/App.vue)） |
| 落地页 + 登录墙（未登录只见首页） | ✅ 已完成（[web/src/Landing.vue](web/src/Landing.vue)） |
| AI 教师答疑（SSE 流式 + 无 key 兜底） | ✅ 已完成（[server/app/tutor.py](server/app/tutor.py)） |
| 管理员控制台（用户 / 角色 / 统计） | ✅ 最小版已完成（[web/src/components/AdminPanel.vue](web/src/components/AdminPanel.vue)） |
| DeepSeek 编排（真实 key 端到端） | ⬜ 待你填 key 验证 |
| pcap 解析（上传 → 会话/报文/字段树/时序图联动 → 变成动画） | ✅ 最小版已完成（[server/app/pcap.py](server/app/pcap.py)） |
| 登录 / 注册 / JWT / BYOK 设置 | ✅ 已完成（[server/app/auth.py](server/app/auth.py)） |
| 数据库：Docker 起 PostgreSQL 16 | ✅ 已完成并实测（[deploy/](deploy/docker-compose.yml)） |
| Hex 高亮、TCP 流重组、实验评测 | ⬜ 设计已写，代码未开始 |

## 三条命令跑起来

```bash
# 0) 依赖（首次）
#    pip install -r server/requirements.txt

# 0.5) 数据库（推荐）：Docker 起 PostgreSQL 16
docker compose -f deploy/docker-compose.yml up -d
#    首次启动会自动建表 + 写入演示账号 demo@lab.test / demo1234
#    不启动也能跑——此时自动退回 SQLite（server/data/app.db）

# 1) 后端（8000）
#    连 Docker PG：
cd server
export DATABASE_URL="postgresql://lab:lab_dev_pwd@127.0.0.1:5432/protocol_lab"
python -m uvicorn app.main:app --reload --port 8000
#    用 SQLite：不 export 这行 DATABASE_URL 即可（自动建 server/data/app.db）

# 2) 前端（5173，已配好 /api 与 /media 代理）
cd web && npm install --ignore-scripts && npm run dev

# 3) 出片用（可选，前端点"导出 MP4"时才需要）
#    renderer 依赖已装好，首次渲染会自动下载 Chrome Headless Shell
```

打开 <http://localhost:5173>，未登录时只有落地页（项目目的 / 功能 / 原理），右上角点「登录」后进入工作台。
用 **admin@lab.test / admin1234** 登录（后端启动时自动创建的内置管理员，见下一节「内置管理员账号」），
或在「模型设置」里填 DeepSeek 的 key 用一句话生成任意知识点、让 AI 教师给出真实模型回答。
`curl http://127.0.0.1:8000/api/health` 会回 `"db":"postgresql"` 或 `"sqlite"`，一眼看出连的是哪个库。

> Windows 两条坑（已写进 [renderer/README.md](renderer/README.md)）：
> `npm install` 要加 `--ignore-scripts`（esbuild 的 postinstall 会 spawn EPERM）；
> 渲染/构建时把 `TEMP`、`TMP` 指到工程内的临时目录，否则 ffmpeg 打不开系统 TEMP。

## 内置管理员账号

后端**每次启动**都会检查管理员账号是否存在（`server/app/main.py` 的 `ensure_builtin_admin()`），
不依赖 Docker 初始化脚本，所以 SQLite 与 PostgreSQL 两条路都生效；换机、清库、换库之后也不会出现"没有管理员"的死局。

| 账号 | 口令 | 说明 |
| --- | --- | --- |
| `admin@lab.test` | `admin1234` | **内置管理员**，后端启动时自动创建（本期默认） |
| `demo@lab.test` | `demo1234` | 演示账号，PG 首次建库时由 `deploy/db/init/03_seed.sql` 写入，同样是管理员 |

启动日志会打印一行确认：

```
[init] created builtin admin: admin@lab.test / admin1234      # 首次创建
[init] builtin admin ready: admin@lab.test                    # 已存在且是管理员
[init] promoted existing account to admin: admin@lab.test     # 账号存在但不是管理员，自动提升
```

- **换账号 / 换口令**：启动前设环境变量 `ADMIN_EMAIL`、`ADMIN_PASSWORD`（答辩机器上可以改成自己的邮箱）。
- **让普通账号变管理员**：`python tools/promote_admin.py 你的邮箱@xx.com`，或登录后在「管理」面板点「设为管理员」。
- **管理端能做什么**：顶栏「管理」→ 用户列表 / 角色切换 / 用量统计。非 admin 访问 `/api/admin/*` 一律 403；管理员不能修改自己的角色（返回 400，防误操作把自己降权）。
- **重启后要重新登录**：JWT 密钥默认每个进程随机生成。想让重启后会话不失效，启动时加 `APP_SECRET=<任意长字符串>`。

## 目录结构

```
docs/设计文档.md      # 答辩主文档（架构 / DDL / 接口 / 演示脚本 / Q&A）
renderer/             # Remotion 工程：props → 帧，一份代码两种产物（Player / MP4）
  src/schema/animation.ts    # Zod 契约（与后端 pydantic 一一对应）
  src/compositions/Handshake.tsx  # 通用"两方消息时序"模板
deploy/               # 数据库：docker compose 起 PG16 + 首次启动自动建表/种子账号
  docker-compose.yml  # 一条命令起库（默认走国内镜像站，可用 PG_IMAGE 覆盖）
  db/init/            # 01 扩展 / 02 表结构 / 03 种子账号（demo@lab.test，admin）
server/               # FastAPI：规则库 + DeepSeek 编排 + SQLite/PG 双驱动 + 渲染任务
  app/db.py           # 存储层：DATABASE_URL 决定 SQLite 还是 PostgreSQL
  app/auth.py         # 注册/登录：PBKDF2 20 万次 + HS256 JWT
  app/main.py         # 启动时 ensure_builtin_admin() 兜底创建 admin@lab.test
  app/planner.py      # 需求 → props 的编排与重试
  app/llm.py          # OpenAI 兼容调用（DeepSeek 默认）
  app/library/        # 六个知识点的剧本构造器
  app/pcap.py         # pcap/pcapng 解析 → 会话 / 报文 / 字段（Wireshark 同名路径）
  app/from_capture.py # 把一段真实会话翻译成 AnimationProps
  app/tutor.py        # AI 教师（B1）：结构化上下文 + SSE 流式 + 无 key 兜底
web/                  # Vue3 前端
  src/Landing.vue     # 未登录落地页（唯一出口是登录/注册）
  src/AuthModal.vue   # 登录 / 注册弹窗（落地页与登录墙共用）
  src/App.vue         # 登录后的工作台：知识点动画 / 抓包解析 / AI 教师
  src/components/TutorPanel.vue  # AI 教师对话面板
  src/components/AdminPanel.vue  # 管理员控制台（用户 / 角色 / 统计）
samples/              # 演示用抓包文件（http-handshake.pcap，12 个报文）
tools/browsercheck/   # 开发期用 Chrome Headless 断言 DOM + 截图（不进产品）
  landing.js          # 落地页 → 登录 → 工作台 → 答疑 → 管理员 → 退出 全链路断言
tools/make_sample_pcap.py  # 重新生成 samples/ 下的样例 pcap
tools/make_seed_user.py    # 生成种子账号口令哈希（与 auth.py 同一算法）
tools/promote_admin.py     # 把任意账号提升为管理员（--list 看全部账号）
```

## 未登录 / 登录后（登录墙）

未登录时**整站只渲染落地页**：导航、首屏、四张功能卡、原理区与页脚，"功能"卡片点击也只会唤起登录框。
工作台（Vue 的 `App` 主分支）压根不挂载，所以未登录连知识点目录都不会去请求——不是拿 CSS 盖住。

登录后顶栏出现三个标签：

| 标签 | 作用 |
| --- | --- |
| 知识点动画 | 选目录里的知识点或一句话描述，生成 / 播放 / 导出 MP4 |
| 抓包解析 | 上传 pcap，三视图联动，把某段会话变成动画 |
| AI 教师 | 左边保留当前剧本当"板书"，右边对话答疑（SSE 流式输出） |

管理员（`role = 'admin'`）额外看到「管理」按钮：用户列表、角色升降、以及用户/动画/抓包/数据库总量。
种子账号 `demo@lab.test` 已设为管理员；其他账号可以通过管理员面板提升，不能自己降自己（避免把唯一管理员锁在门外）。

`tools/browsercheck/landing.js` 是这条链路的自检脚本（21 条 DOM 断言，含登录墙、弹窗尺寸、SSE 回答非空、管理员面板行数、退出回落）。

## 抓包解析（第二个入口）

顶部切到「抓包解析」，把 `.pcap` / `.pcapng` 拖进去（或点「选择文件」）。没有现成文件时，
仓库里带了一份 `samples/http-handshake.pcap`（ARP + TCP 握手 + HTTP 请求 + 四次挥手，12 个报文）。

界面是"一份状态、三处联动"：

- 左：会话列表（按五元组自动切分，中文命名，如「HTTP 请求 / 响应」）
- 中：报文列表（序号 / 时间 / 摘要 / 长度）
- 右：时序图（箭头方向就是发包方向）+ 字段树（`ip.src` / `tcp.flags.syn` 这类 Wireshark 同名路径）

点报文列表里任意一行，右边时序图的对应箭头和字段树同时跳过去；点时序图上的箭头也会反向选中那一行。
底部调好时长后点「把这个会话变成动画 →」，就会用这段**真实报文**生成一段动画——和知识库那六个主题
走的是同一个渲染器、同一份 props 契约。

边界（答辩时主动说）：只解析单个文件、最多 5000 个报文 / 12 MB；不做 TCP 流重组（payload 只给可打印预览）；
不做 Hex 高亮；只覆盖 IPv4 / IPv6 / TCP / UDP / ICMP / ARP。

## AI 教师（B1）

切到「AI 教师」：左边还是当前剧本的播放器（当板书用），右边是对话。

关键设计是**不把整份剧本丢给模型**：`server/app/tutor.py` 先把它折成"场景标题 + 旁白 + 报文关键字段"
（几百 token），再让模型在这份事实里讲课。系统提示明确要求"必须用上下文里的真实数字，没有的信息就说需要查证"。

- 流式：`POST /api/tutor/ask` 走 SSE，前端用 fetch + ReadableStream 解析（EventSource 只能 GET，放不下问题与历史）
- 降级：没有可用 key 时**仍返回 200**，内容是规则拼的要点（`offline_answer`），答辩断网也能演示
- 切换知识点会清空对话——上下文变了，旧回答会误导

## 设计要点

1. **模型只编排，不写代码**：DeepSeek 产出的是 `AnimationProps` JSON，渲染端用同一份
   Zod / pydantic 契约校验；线上请求链路**从不执行**模型生成的代码（对应设计文档 4.6.2）。
2. **预览与成片同源**：浏览器里跑的是 `<Player>`，出片跑的是 `@remotion/renderer`，
   加载的是同一个 Composition 组件，所以"预览什么样，MP4 就什么样"。
3. **两条生成路径，一份契约**：规则库（离线、秒出、答辩断网可用）+ 大模型（需求泛化），
   出口都经过同样的结构校验与时长重排。
4. **三个界面共用一份事实**：动画、抓包、AI 教师看到的是同一份结构化数据，所以"画面上标的 seq"
   和"助教嘴里说的 seq"不会打架。
5. **权限边界在服务端**：前端隐藏按钮只是体验，真正的判定是 `require_admin` 依赖；未登录的请求
   在 `App` 主分支根本不发起，但接口本身也靠 `require_user` 兜底。

## 限制（答辩时主动说，别等评委问）

- 模板是"两方消息时序图"，画面只有两列；DNS 那种多方接力靠旁白补足，不会凭空多出第三个角色。
- 没有配音，只有字幕与按帧排的时间轴。
- AI 教师目前只按"当前知识点 + 当前剧本"回答，没有跨会话记忆，也没有接入外部知识库（设计文档里的 RAG 未实现）。
- 管理员端是最小版：只做了用户与角色，模型配置仍是 BYOK、限流与审计日志未做。
- SQLite 是零依赖备选；PostgreSQL 已是默认实测路径（`deploy/` 一条命令起库），向量检索尚未接入。
- 只有三视图（报文列表 / 时序图 / 字段树），Hex 高亮与 TCP 流重组只有设计没有代码。
- AI 教师**没有**做引用校验与数字比对：靠"上下文里只放真实字段 + 提示词要求不许编"来约束，
  设计文档 4.9.5 有明确的"本期 vs 目标"对照表，答辩时按那个口径讲。
- 实验与评测（设计文档 4.5）整节是设计目标，没有实现；所以也没有学习效果数据。
