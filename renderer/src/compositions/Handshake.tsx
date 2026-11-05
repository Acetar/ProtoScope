import React, {useMemo} from 'react';
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {ActorCard} from '../components/ActorCard';
import {Background} from '../components/Background';
import {Caption} from '../components/Caption';
import {InfoPanel, type FieldRow} from '../components/InfoPanel';
import {Packet} from '../components/Packet';
import {ProgressBar} from '../components/ProgressBar';
import {COLORS, FONT, MONO} from '../lib/theme';
import {
  parseProps,
  type Actor,
  type AnimationProps,
  type PacketFlyAction,
  type Scene,
} from '../schema/animation';

const ACTOR_HALF = 130;
const FIRST_MSG_Y = 430;
const MSG_GAP = 130;
const LIFELINE_BOTTOM = 900;
/** 报文胶囊抬到箭线上方，避免盖住箭头 */
const PACKET_LIFT = 44;

type MessageGeom = {
  scene: Scene;
  packet: PacketFlyAction;
  y: number;
  startX: number;
  endX: number;
  dir: 1 | -1;
};

function packetOf(scene: Scene): PacketFlyAction | undefined {
  return scene.actions.find((a): a is PacketFlyAction => a.type === 'packet-fly');
}

function fieldsText(packet: PacketFlyAction): string {
  return Object.entries(packet.fields)
    .filter(([, v]) => Boolean(v))
    .map(([k, v]) => `${k}=${v}`)
    .join(' · ');
}

function fieldRows(packet?: PacketFlyAction): FieldRow[] {
  if (!packet) return [];
  return Object.entries(packet.fields)
    .filter(([, v]) => Boolean(v))
    .map(([k, v]) => ({key: k, value: String(v)}));
}

/** 飞行中的报文：只在自己的 scene 窗口内挂载，读到的 frame 是场景内相对帧 */
const FlyingPacket: React.FC<{
  packet: PacketFlyAction;
  startX: number;
  endX: number;
  y: number;
}> = ({packet, startX, endX, y}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const land = packet.delay + packet.durationInFrames;

  const t = interpolate(frame, [packet.delay, land], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  const pop = spring({
    frame: Math.max(0, frame - packet.delay),
    fps,
    config: {damping: 13, mass: 0.6, stiffness: 140},
  });

  const opacity = interpolate(frame, [packet.delay, packet.delay + 5, land - 6, land], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <Packet
      label={packet.label}
      fieldsText={fieldsText(packet)}
      color={packet.color}
      x={startX + (endX - startX) * t}
      y={y}
      scale={0.72 + 0.28 * pop}
      opacity={opacity}
    />
  );
};

export const Handshake: React.FC<AnimationProps> = (raw) => {
  const props = useMemo(() => parseProps(raw), [raw]);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const actorsById = useMemo(() => {
    const map: Record<string, Actor> = {};
    for (const a of props.actors) map[a.id] = a;
    return map;
  }, [props.actors]);

  /** 消息几何：第 i 条消息在第 i 个纵向轨道上 */
  const messages = useMemo(() => {
    const out: MessageGeom[] = [];
    // 4 条以上消息时压缩行距，避免最后一条压到字幕
    const dense = props.scenes.length >= 4;
    const firstY = dense ? 400 : FIRST_MSG_Y;
    const gap = dense ? 108 : MSG_GAP;
    props.scenes.forEach((scene, i) => {
      const packet = packetOf(scene);
      if (!packet) return;
      const from = actorsById[packet.from];
      const to = actorsById[packet.to];
      if (!from || !to) return;
      const dir: 1 | -1 = to.x >= from.x ? 1 : -1;
      out.push({
        scene,
        packet,
        y: firstY + i * gap,
        startX: from.x + dir * (ACTOR_HALF + 4),
        endX: to.x - dir * (ACTOR_HALF + 4),
        dir,
      });
    });
    return out;
  }, [props.scenes, actorsById]);

  /** 当前协议状态：初始态 + 已经发生的状态切换 */
  const states = useMemo(() => {
    const map: Record<string, string> = {};
    for (const a of props.actors) map[a.id] = a.initialState;
    for (const scene of props.scenes) {
      for (const action of scene.actions) {
        if (action.type === 'state-change' && frame >= scene.startFrame + action.delay) {
          map[action.actor] = action.to;
        }
      }
    }
    return map;
  }, [props.actors, props.scenes, frame]);

  /** 当前步骤 */
  let stepIndex = 0;
  props.scenes.forEach((s, i) => {
    if (frame >= s.startFrame) stepIndex = i;
  });
  const currentScene = props.scenes[stepIndex];
  const currentPacket = packetOf(currentScene);

  /** 卡片高亮：pulse 或刚收到报文 */
  const glow: Record<string, boolean> = {};
  for (const scene of props.scenes) {
    for (const action of scene.actions) {
      if (action.type === 'pulse') {
        const at = scene.startFrame + action.delay;
        if (frame >= at && frame <= at + 24) glow[action.actor] = true;
      }
    }
  }
  for (const m of messages) {
    const land = m.scene.startFrame + m.packet.delay + m.packet.durationInFrames;
    if (frame >= land && frame <= land + 22) glow[m.packet.to] = true;
  }

  const panelOpacity = interpolate(frame, [currentScene.startFrame, currentScene.startFrame + 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const caption = props.captions.find((c) => frame >= c.startFrame && frame <= c.endFrame);
  const captionOpacity = caption
    ? interpolate(
        frame,
        [caption.startFrame, caption.startFrame + 8, caption.endFrame - 8, caption.endFrame],
        [0, 1, 1, 0],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
      )
    : 0;

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: FONT}}>
      <Background />

      {/* 标题区 */}
      <div style={{position: 'absolute', left: 80, top: 54}}>
        <div
          style={{
            display: 'inline-block',
            fontFamily: MONO,
            fontSize: 14,
            letterSpacing: 3,
            color: COLORS.cyan,
            border: '1px solid rgba(56, 225, 255, 0.30)',
            background: 'rgba(56, 225, 255, 0.08)',
            borderRadius: 999,
            padding: '5px 12px',
          }}
        >
          NETWORK PROTOCOL · MOTION
        </div>
        <div
          style={{
            fontSize: 58,
            fontWeight: 700,
            color: COLORS.text,
            letterSpacing: 2,
            marginTop: 14,
            lineHeight: 1.1,
          }}
        >
          {props.title}
        </div>
        <div style={{fontSize: 24, color: COLORS.muted, marginTop: 8, letterSpacing: 1}}>
          {props.subtitle}
        </div>
      </div>

      {/* 两个演员 */}
      {props.actors.map((actor) => (
        <ActorCard
          key={actor.id}
          actor={actor}
          state={states[actor.id] ?? actor.initialState}
          glow={Boolean(glow[actor.id])}
        />
      ))}

      {/* 生命线 */}
      <svg
        width={1920}
        height={1080}
        style={{position: 'absolute', left: 0, top: 0}}
      >
        {props.actors.map((a) => (
          <line
            key={a.id}
            x1={a.x}
            y1={a.y + 76}
            x2={a.x}
            y2={LIFELINE_BOTTOM}
            stroke="rgba(120, 170, 255, 0.22)"
            strokeWidth={2}
            strokeDasharray="6 10"
          />
        ))}
      </svg>

      {/* 消息轨道：已开始的场景亮起，箭头指向接收方 */}
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        {messages.map((m) => {
          const lineOpacity = interpolate(
            frame,
            [m.scene.startFrame, m.scene.startFrame + 14],
            [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
          );
          const head =
            m.dir === 1
              ? `${m.endX - 14},${m.y - 7} ${m.endX},${m.y} ${m.endX - 14},${m.y + 7}`
              : `${m.endX + 14},${m.y - 7} ${m.endX},${m.y} ${m.endX + 14},${m.y + 7}`;
          return (
            <g key={m.scene.id} opacity={lineOpacity}>
              <line
                x1={m.startX}
                y1={m.y}
                x2={m.endX}
                y2={m.y}
                stroke={`${m.packet.color}66`}
                strokeWidth={2}
                strokeDasharray="10 8"
              />
              <polygon points={head} fill={m.packet.color} />
            </g>
          );
        })}
      </svg>

      {/* 飞行报文（场景内动画） */}
      {messages.map((m) => (
        <Sequence
          key={m.scene.id}
          from={m.scene.startFrame}
          durationInFrames={m.scene.durationInFrames}
          name={m.scene.title}
        >
          <FlyingPacket packet={m.packet} startX={m.startX} endX={m.endX} y={m.y - PACKET_LIFT} />
        </Sequence>
      ))}

      {/* 已送达的报文：停留在接收方一侧，作为时序图的"历史消息" */}
      {messages.map((m) => {
        const land = m.scene.startFrame + m.packet.delay + m.packet.durationInFrames;
        const landedOpacity = interpolate(frame, [land, land + 8], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        if (frame < land) return null;
        return (
          <Packet
            key={`landed-${m.scene.id}`}
            label={m.packet.label}
            fieldsText={fieldsText(m.packet)}
            color={m.packet.color}
            x={m.endX}
            y={m.y - PACKET_LIFT}
            scale={1}
            opacity={landedOpacity}
          />
        );
      })}

      {/* 右侧讲解面板：切步骤时淡入 */}
      <div style={{opacity: panelOpacity}}>
        <InfoPanel
          stepIndex={stepIndex}
          totalSteps={props.scenes.length}
          scene={currentScene}
          fields={fieldRows(currentPacket)}
        />
      </div>

      {/* 字幕 */}
      {caption ? (
        <Caption
          text={caption.text}
          opacity={captionOpacity}
          accent={currentPacket?.color ?? COLORS.cyan}
        />
      ) : null}

      {/* 页脚信息 */}
      <div
        style={{
          position: 'absolute',
          left: 90,
          top: 968,
          fontFamily: MONO,
          fontSize: 15,
          letterSpacing: 1.2,
          color: COLORS.dim,
        }}
      >
        knowledge_point={props.knowledgePoint} · template={props.templateId} ·{' '}
        {props.totalFrames}f
      </div>

      <ProgressBar frame={frame} totalFrames={props.totalFrames} fps={fps} />
    </AbsoluteFill>
  );
};
