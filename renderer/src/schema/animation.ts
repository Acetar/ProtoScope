import {z} from 'zod';

/**
 * 动画 props 的单一事实来源。
 *
 * 大模型只产出这份 JSON，不产出组件代码；渲染端在入口处 parse 一次，
 * 结构不合法直接抛错，避免"坏数据"被渲染成奇怪画面。
 */

const PacketFields = z.object({
  seq: z.string().optional(),
  ack: z.string().optional(),
  flags: z.string().optional(),
  len: z.string().optional(),
});

/** 报文沿箭头飞行 */
const PacketFly = z.object({
  type: z.literal('packet-fly'),
  from: z.string(),
  to: z.string(),
  label: z.string(),
  delay: z.number().int().nonnegative(),
  durationInFrames: z.number().int().positive(),
  fields: PacketFields,
  color: z.string(),
});

/** 演员状态切换（如 SYN_SENT → ESTABLISHED） */
const StateChange = z.object({
  type: z.literal('state-change'),
  actor: z.string(),
  from: z.string(),
  to: z.string(),
  delay: z.number().int().nonnegative(),
});

/** 演员卡片高亮脉冲 */
const Pulse = z.object({
  type: z.literal('pulse'),
  actor: z.string(),
  delay: z.number().int().nonnegative(),
});

/** 旁挂批注气泡 */
const Callout = z.object({
  type: z.literal('callout'),
  actor: z.string(),
  text: z.string(),
  delay: z.number().int().nonnegative(),
});

export const Action = z.discriminatedUnion('type', [
  PacketFly,
  StateChange,
  Pulse,
  Callout,
]);
export type Action = z.infer<typeof Action>;
export type PacketFlyAction = z.infer<typeof PacketFly>;

export const Scene = z.object({
  id: z.string(),
  title: z.string(),
  startFrame: z.number().int().nonnegative(),
  durationInFrames: z.number().int().positive(),
  /** 讲解词：信息面板展示，也可作为 TTS 文本 */
  narration: z.string(),
  actions: z.array(Action),
});
export type Scene = z.infer<typeof Scene>;

export const Actor = z.object({
  id: z.string(),
  label: z.string(),
  icon: z.enum(['laptop', 'server', 'cloud', 'router']),
  /** 卡片中心坐标（1920x1080 画布） */
  x: z.number(),
  y: z.number(),
  initialState: z.string(),
});
export type Actor = z.infer<typeof Actor>;

export const Caption = z.object({
  startFrame: z.number().int().nonnegative(),
  endFrame: z.number().int().nonnegative(),
  text: z.string(),
});
export type Caption = z.infer<typeof Caption>;

export const AnimationProps = z.object({
  /** 知识点标识，如 tcp.handshake */
  knowledgePoint: z.string(),
  /** Composition 模板 id，与 Root.tsx 注册的 id 对应 */
  templateId: z.string(),
  title: z.string(),
  subtitle: z.string(),
  fps: z.literal(30),
  width: z.literal(1920),
  height: z.literal(1080),
  totalFrames: z.number().int().positive(),
  actors: z.array(Actor).min(2),
  scenes: z.array(Scene).min(1),
  captions: z.array(Caption),
  /** 旁白音频（可空：demo 不带音频，生产由 edge-tts 生成） */
  audioSrc: z.string().nullable(),
});

export type AnimationProps = z.infer<typeof AnimationProps>;

/** 渲染端入口用：解析失败时错误信息更可读 */
export function parseProps(input: unknown): AnimationProps {
  const result = AnimationProps.safeParse(input);
  if (!result.success) {
    throw new Error(
      `[animation-props] 校验失败: ${result.error.issues
        .map((i) => `${i.path.join('.')}: ${i.message}`)
        .join('; ')}`,
    );
  }
  return result.data;
}
