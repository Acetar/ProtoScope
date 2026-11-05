import React from 'react';
import {COLORS, MONO} from '../lib/theme';

type Props = {
  frame: number;
  totalFrames: number;
  fps: number;
};

function timecode(frame: number, fps: number): string {
  const totalSeconds = frame / fps;
  const m = Math.floor(totalSeconds / 60);
  const s = Math.floor(totalSeconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const ProgressBar: React.FC<Props> = ({frame, totalFrames, fps}) => {
  const pct = Math.max(0, Math.min(1, frame / totalFrames));
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 90,
          top: 1014,
          width: 1740,
          height: 4,
          borderRadius: 999,
          background: 'rgba(255, 255, 255, 0.09)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct * 100}%`,
            height: '100%',
            borderRadius: 999,
            background: `linear-gradient(90deg, ${COLORS.cyan}, ${COLORS.green})`,
          }}
        />
      </div>
      <div
        style={{
          position: 'absolute',
          right: 90,
          top: 968,
          fontFamily: MONO,
          fontSize: 16,
          letterSpacing: 1,
          color: COLORS.dim,
        }}
      >
        {timecode(frame, fps)} / {timecode(totalFrames, fps)} · 30fps
      </div>
    </>
  );
};
