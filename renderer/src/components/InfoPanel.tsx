import React from 'react';
import {COLORS, FONT, MONO} from '../lib/theme';
import type {Scene} from '../schema/animation';

export type FieldRow = {key: string; value: string};

type Props = {
  stepIndex: number;
  totalSteps: number;
  scene: Scene;
  fields: FieldRow[];
};

/**
 * 右侧信息面板：当前步骤 + 讲解词 + 关键字段。
 * 这块是"教学"属性的载体，避免动画只剩好看。
 */
export const InfoPanel: React.FC<Props> = ({stepIndex, totalSteps, scene, fields}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: 1220,
        top: 150,
        width: 620,
        minHeight: 540,
        boxSizing: 'border-box',
        padding: '32px 34px',
        borderRadius: 26,
        background: 'rgba(13, 21, 40, 0.88)',
        border: `1px solid ${COLORS.border}`,
        boxShadow: '0 24px 60px rgba(0, 0, 0, 0.35)',
        fontFamily: FONT,
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
        <span
          style={{
            fontFamily: MONO,
            fontSize: 15,
            letterSpacing: 2,
            color: COLORS.cyan,
            background: 'rgba(56, 225, 255, 0.10)',
            border: '1px solid rgba(56, 225, 255, 0.28)',
            borderRadius: 999,
            padding: '6px 14px',
          }}
        >
          STEP {String(stepIndex + 1).padStart(2, '0')} / {String(totalSteps).padStart(2, '0')}
        </span>
        <span style={{fontSize: 14, letterSpacing: 1.5, color: COLORS.dim}}>AI 编排</span>
      </div>

      <div style={{fontSize: 36, fontWeight: 700, color: COLORS.text, marginTop: 22, letterSpacing: 0.5}}>
        {scene.title}
      </div>

      <div style={{fontSize: 23, lineHeight: 1.75, color: '#a9bcd8', marginTop: 14}}>
        {scene.narration}
      </div>

      <div
        style={{
          height: 1,
          background: 'rgba(110, 160, 255, 0.16)',
          margin: '26px 0 22px',
        }}
      />

      <div style={{fontSize: 14, letterSpacing: 3, color: COLORS.dim}}>关键字段</div>

      <div style={{marginTop: 6}}>
        {fields.length === 0 ? (
          <div style={{fontSize: 18, color: COLORS.dim, padding: '12px 0'}}>—</div>
        ) : (
          fields.map((f) => (
            <div
              key={f.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '11px 0',
                borderBottom: '1px solid rgba(110, 160, 255, 0.10)',
              }}
            >
              <span style={{fontFamily: MONO, fontSize: 18, color: COLORS.muted}}>{f.key}</span>
              <span style={{fontFamily: MONO, fontSize: 20, color: COLORS.text}}>{f.value}</span>
            </div>
          ))
        )}
      </div>

      <div style={{fontSize: 14, color: COLORS.dim, marginTop: 26, letterSpacing: 0.5}}>
        props 驱动 · 渲染端不执行模型生成的代码
      </div>
    </div>
  );
};
