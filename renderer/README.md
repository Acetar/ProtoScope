# ProtoLearn Renderer · Remotion Demo

设计文档 [4.6 AI 动效科普](../docs/设计文档.md) 的最小可运行实现：
**大模型只产 props JSON，Remotion Composition 负责画面，同一份代码既能浏览器预览、也能服务端出片。**

当前内置一个模板：`Handshake`（TCP 三次握手，18s / 30fps / 1920×1080）。

## 快速开始

```bash
cd renderer
npm install

npm run studio     # 打开 Remotion Studio，浏览器里逐帧拖时间轴
npm run still      # 导出第 150 帧 PNG → out/frame.png
npm run render     # 导出整段 MP4 → out/handshake.mp4
npm run typecheck  # tsc --noEmit
```

> 首次执行 `still` / `render` 会自动下载 Chrome Headless Shell（约 150 MB），
> 国内网络可能较慢；Studio 预览不需要下载。

### Windows 沙箱下的已知坑

如果 `npm run render` 报 `FFmpeg ... Permission denied`（临时目录不可写），
把系统临时目录指到工程内再跑：

```bash
mkdir -p .tmp
TEMP="$(pwd)/.tmp" TMP="$(pwd)/.tmp" npx remotion render src/index.ts Handshake out/handshake.mp4
```

另外 `npm install` 若卡在 `esbuild postinstall` 的 `spawn EPERM`，
用 `npm install --ignore-scripts`：esbuild / Remotion 的平台二进制本就是
optionalDependency，跳过生命周期脚本不影响运行。

## 目录结构

```
renderer/
├── remotion.config.ts        # 输出格式、并发数
├── src/
│   ├── index.ts              # registerRoot 入口
│   ├── Root.tsx              # Composition 注册表（id ↔ 模板）
│   ├── schema/animation.ts   # Zod 契约：props 的单一事实来源
│   ├── props/handshake.ts    # 默认 props（生产中由 LLM 生成）
│   ├── compositions/
│   │   └── Handshake.tsx     # 三次握手：轨道 + 报文 + 状态机
│   ├── components/           # 纯展示组件，不含业务判断
│   │   ├── Background.tsx
│   │   ├── ActorCard.tsx
│   │   ├── Packet.tsx
│   │   ├── InfoPanel.tsx
│   │   ├── Caption.tsx
│   │   └── ProgressBar.tsx
│   └── lib/theme.ts          # 颜色 / 字体常量
└── out/                      # 渲染产物（gitignore）
```

## 数据流

```
LLM 生成 JSON ──► Zod parseProps() ──► <Handshake {...props} />
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
            @remotion/player（浏览器预览）          @remotion/renderer（Node 出片）
```

关键约束：

1. **渲染端不执行模型生成的代码**。模型只能改 JSON 里的文案、坐标、时长、颜色；
   组件代码由人维护，这是 4.6 里"路线 A"的边界。
2. props 在组件入口 `parseProps()` 校验一次，结构不合法直接抛错，
   不会把坏数据渲染成奇怪画面。
3. 所有动画都是 `useCurrentFrame()` 的纯函数，没有 `Math.random()` / `Date.now()`，
   保证同 props 同版本逐帧可复现。

## props 契约（节选）

完整定义见 `src/schema/animation.ts`。一条消息对应一个 scene：

```json
{
  "knowledgePoint": "tcp.handshake",
  "templateId": "Handshake",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "totalFrames": 540,
  "actors": [
    {"id": "client", "label": "客户端", "icon": "laptop", "x": 300, "y": 170, "initialState": "CLOSED"},
    {"id": "server", "label": "服务端", "icon": "server", "x": 1000, "y": 170, "initialState": "LISTEN"}
  ],
  "scenes": [
    {
      "id": "scene-1",
      "title": "第一次握手 · SYN",
      "startFrame": 0,
      "durationInFrames": 180,
      "narration": "客户端请求建立连接，携带初始序号 ISN(c)=100。",
      "actions": [
        {"type": "packet-fly", "from": "client", "to": "server", "label": "SYN",
         "delay": 20, "durationInFrames": 60,
         "fields": {"seq": "100", "flags": "SYN"}, "color": "#ffb454"},
        {"type": "state-change", "actor": "client", "from": "CLOSED", "to": "SYN_SENT", "delay": 20}
      ]
    }
  ],
  "captions": [{"startFrame": 24, "endFrame": 150, "text": "① 客户端发送 SYN…"}],
  "audioSrc": null
}
```

## 与设计文档 4.6 的差距

已实现：props 驱动、Zod 校验、场景/动作编排、状态机、字幕、进度条、确定性渲染。

未实现（生产补齐）：

- `audioSrc` 播放与 `getAudioDurationInSeconds()` 回填时长（demo 无音频）
- 另外 7 个模板（DNS / HTTP / 丢包重传 / 逐跳 / 对比 …）
- Player 外层交互（点击报文暂停、字段高亮联动）
- 渲染服务（Fastify + `@remotion/renderer` + 队列 + MinIO）
- 黄金帧像素对比回归

## 加一个新模板

1. `src/compositions/<Name>.tsx`，props 类型复用 `AnimationProps`（或扩展字段）。
2. `src/props/<name>.ts` 写默认 props。
3. `src/Root.tsx` 注册 `<Composition id="<Name>" ... />`。
4. `templateId` 与 Composition id 保持一致，前端 Player 按 id 查找。
