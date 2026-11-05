import React from 'react';
import {COLORS, FONT, MONO} from '../lib/theme';
import type {Actor} from '../schema/animation';

const ICON_PROPS = {
  width: 44,
  height: 44,
  viewBox: '0 0 44 44',
  fill: 'none',
  stroke: '#8fd8ff',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

const LaptopIcon: React.FC = () => (
  <svg {...ICON_PROPS}>
    <rect x="8" y="8" width="28" height="20" rx="2.5" />
    <path d="M3 33h38" />
    <path d="M18 14h8" />
  </svg>
);

const ServerIcon: React.FC = () => (
  <svg {...ICON_PROPS}>
    <rect x="8" y="5" width="28" height="10" rx="2" />
    <rect x="8" y="17" width="28" height="10" rx="2" />
    <rect x="8" y="29" width="28" height="10" rx="2" />
    <circle cx="14" cy="10" r="1.2" fill="#8fd8ff" />
    <circle cx="14" cy="22" r="1.2" fill="#8fd8ff" />
    <circle cx="14" cy="34" r="1.2" fill="#8fd8ff" />
  </svg>
);

const CloudIcon: React.FC = () => (
  <svg {...ICON_PROPS}>
    <path d="M12 30a7 7 0 0 1 .6-14 9 9 0 0 1 17.2 1.6A6 6 0 0 1 32 30z" />
  </svg>
);

const RouterIcon: React.FC = () => (
  <svg {...ICON_PROPS}>
    <rect x="6" y="22" width="32" height="12" rx="3" />
    <path d="M14 22V9m0 0l-4 4m4-4l4 4" />
  </svg>
);

function Icon({name}: {name: Actor['icon']}) {
  switch (name) {
    case 'laptop':
      return <LaptopIcon />;
    case 'server':
      return <ServerIcon />;
    case 'cloud':
      return <CloudIcon />;
    case 'router':
      return <RouterIcon />;
    default:
      return null;
  }
}

export function stateColor(state: string): string {
  if (state === 'ESTABLISHED') return COLORS.green;
  if (state.startsWith('SYN')) return COLORS.amber;
  if (state === 'CLOSED' || state === 'LISTEN') return COLORS.dim;
  return COLORS.cyan;
}

type Props = {
  actor: Actor;
  state: string;
  glow: boolean;
};

export const ActorCard: React.FC<Props> = ({actor, state, glow}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: actor.x - 130,
        top: actor.y - 56,
        width: 260,
        height: 112,
        borderRadius: 22,
        background: COLORS.card,
        border: `1px solid ${glow ? 'rgba(56, 225, 255, 0.75)' : COLORS.border}`,
        boxShadow: glow
          ? '0 0 0 1px rgba(56,225,255,0.35), 0 0 48px rgba(56,225,255,0.35)'
          : '0 18px 40px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 24px',
        boxSizing: 'border-box',
        fontFamily: FONT,
      }}
    >
      <Icon name={actor.icon} />
      <div style={{display: 'flex', flexDirection: 'column', gap: 4}}>
        <span
          style={{
            fontSize: 24,
            fontWeight: 600,
            color: COLORS.text,
            letterSpacing: 0.5,
            whiteSpace: 'nowrap',
          }}
        >
          {actor.label}
        </span>
        <span style={{fontSize: 16, color: COLORS.dim, letterSpacing: 1.2}}>
          {actor.id.toUpperCase()}
        </span>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 118,
          textAlign: 'center',
          fontFamily: MONO,
          fontSize: 18,
          letterSpacing: 1.5,
          color: stateColor(state),
        }}
      >
        {state}
      </div>
    </div>
  );
};
