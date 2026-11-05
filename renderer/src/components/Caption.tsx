import React from 'react';
import {FONT} from '../lib/theme';

type Props = {
  text: string;
  opacity: number;
  accent: string;
};

/** 底部字幕条，替代 TTS 的视觉兜底 */
export const Caption: React.FC<Props> = ({text, opacity, accent}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: 90,
        top: 786,
        width: 1080,
        boxSizing: 'border-box',
        opacity,
        padding: '16px 24px',
        borderRadius: 14,
        borderLeft: `3px solid ${accent}`,
        background: 'rgba(9, 15, 30, 0.78)',
        fontFamily: FONT,
        fontSize: 26,
        lineHeight: 1.5,
        color: '#dbe6ff',
        letterSpacing: 0.5,
      }}
    >
      {text}
    </div>
  );
};
