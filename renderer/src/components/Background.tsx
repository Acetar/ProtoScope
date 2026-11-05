import React from 'react';
import {AbsoluteFill} from 'remotion';
import {COLORS} from '../lib/theme';

/**
 * 画布背景：深色底 + 两团柔光 + 细网格。
 * 网格只在中部可见，避免抢主体。
 */
export const Background: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(1100px 700px at 18% 8%, rgba(56, 225, 255, 0.12), transparent 62%),' +
            'radial-gradient(900px 600px at 88% 92%, rgba(61, 220, 151, 0.10), transparent 60%)',
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            'linear-gradient(rgba(110, 160, 255, 0.07) 1px, transparent 1px),' +
            'linear-gradient(90deg, rgba(110, 160, 255, 0.07) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
          maskImage:
            'radial-gradient(1200px 820px at 50% 46%, rgba(0,0,0,1) 35%, rgba(0,0,0,0) 88%)',
          WebkitMaskImage:
            'radial-gradient(1200px 820px at 50% 46%, rgba(0,0,0,1) 35%, rgba(0,0,0,0) 88%)',
        }}
      />
    </AbsoluteFill>
  );
};
