import React from 'react';
import {FONT, MONO} from '../lib/theme';

type Props = {
  label: string;
  fieldsText: string;
  color: string;
  x: number;
  y: number;
  scale: number;
  opacity: number;
};

/**
 * 飞行中的报文胶囊：位置由外部逐帧算好，这里只负责长相。
 */
export const Packet: React.FC<Props> = ({
  label,
  fieldsText,
  color,
  x,
  y,
  scale,
  opacity,
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        opacity,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '11px 22px 11px 18px',
        borderRadius: 999,
        border: `1px solid ${color}aa`,
        background: `linear-gradient(135deg, ${color}2e, rgba(9, 15, 28, 0.96))`,
        boxShadow: `0 0 34px ${color}55, 0 12px 28px rgba(0, 0, 0, 0.45)`,
        whiteSpace: 'nowrap',
        fontFamily: FONT,
      }}
    >
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: 999,
          backgroundColor: color,
          boxShadow: `0 0 12px ${color}`,
          flexShrink: 0,
        }}
      />
      <span style={{fontSize: 26, fontWeight: 600, color: '#ffffff', letterSpacing: 0.5}}>
        {label}
      </span>
      {fieldsText ? (
        <span style={{fontFamily: MONO, fontSize: 17, color: 'rgba(214, 232, 255, 0.82)'}}>
          {fieldsText}
        </span>
      ) : null}
    </div>
  );
};
