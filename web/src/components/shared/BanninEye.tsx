'use client';

import { useId } from 'react';

interface BanninEyeProps {
  size?: number;
}

export function BanninEye({ size = 28 }: BanninEyeProps) {
  const reactId = useId();
  const id = `bannin-eye-${reactId.replace(/:/g, '')}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Bannin logo"
      className="bannin-eye"
    >
      <defs>
        <radialGradient id={`${id}-bg`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#1a1a2e" />
          <stop offset="100%" stopColor="#0a0a14" />
        </radialGradient>
        <radialGradient id={`${id}-iris`} cx="50%" cy="45%" r="40%">
          <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.9" />
          <stop offset="60%" stopColor="#0097a7" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#004d5a" stopOpacity="0.3" />
        </radialGradient>
        <radialGradient id={`${id}-depth`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#00b8d4" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#00b8d4" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Outer glow -- breathing animation target */}
      <circle
        cx="32"
        cy="32"
        r="30"
        fill="none"
        stroke="#00e5ff"
        strokeWidth="1"
        opacity="0.25"
        className="bannin-eye__glow"
      />

      {/* Dark sphere background */}
      <circle cx="32" cy="32" r="26" fill={`url(#${id}-bg)`} />

      {/* Depth glow layer */}
      <circle cx="32" cy="32" r="20" fill={`url(#${id}-depth)`} className="bannin-eye__glow" />

      {/* Iris ring */}
      <circle
        cx="32"
        cy="32"
        r="14"
        fill="none"
        stroke="#00e5ff"
        strokeWidth="2.5"
        opacity="0.85"
      />
      <circle cx="32" cy="32" r="12" fill={`url(#${id}-iris)`} />

      {/* Dark pupil */}
      <circle cx="32" cy="32" r="5.5" fill="#0a0a14" />

      {/* Specular highlight */}
      <circle cx="27" cy="27" r="2" fill="white" opacity="0.3" />

      <style>{`
        .bannin-eye__glow {
          animation: banninBreathe 2s ease-in-out infinite;
        }
        @keyframes banninBreathe {
          0%, 100% { opacity: 0.25; transform-origin: center; transform: scale(1); }
          50% { opacity: 0.55; transform-origin: center; transform: scale(1.04); }
        }
        @media (prefers-reduced-motion: reduce) {
          .bannin-eye__glow { animation: none; }
        }
      `}</style>
    </svg>
  );
}
