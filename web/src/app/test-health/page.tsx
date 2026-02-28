'use client';

import { useState } from 'react';
import { ConversationHealth } from '@/components/dashboard/ConversationHealth';
import type { ConversationHealth as ConversationHealthType } from '@/types';

const SCENARIOS: Record<string, ConversationHealthType | null> = {
  idle: null,

  healthy: {
    healthScore: 92,
    rating: 'excellent',
    source: 'Claude Code - MCP',
    components: {
      context_freshness: { score: 95, weight: 0.25, detail: 'Plenty of room remaining' },
      session_fatigue: { score: 88, weight: 0.35, detail: 'Session is healthy -- everything running smoothly' },
      chat_quality: { score: 90, weight: 0.25, detail: 'Quality is excellent' },
    },
    recommendation: null,
  },

  fair: {
    healthScore: 58,
    rating: 'fair',
    source: 'Cursor - MCP',
    components: {
      context_freshness: { score: 52, weight: 0.25, detail: '62% of context window used' },
      session_fatigue: { score: 55, weight: 0.35, detail: 'Session has been running for 45 minutes with 80 tool calls' },
      chat_quality: { score: 68, weight: 0.25, detail: 'Quality may start declining soon' },
    },
    recommendation: 'Keep an eye on quality -- it may start declining as the conversation grows.',
  },

  poor: {
    healthScore: 25,
    rating: 'poor',
    source: 'Claude Code - JSONL',
    components: {
      context_freshness: { score: 15, weight: 0.25, detail: 'Context window nearly full -- 88% used' },
      session_fatigue: { score: 30, weight: 0.35, detail: 'Very long session -- quality is degrading' },
      chat_quality: { score: 35, weight: 0.25, detail: 'Responses becoming less coherent' },
    },
    recommendation: 'Start a new conversation for best results.',
  },
};

export default function TestHealthPage() {
  const [scenario, setScenario] = useState<string>('fair');

  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0f', padding: '40px' }}>
      <div style={{ maxWidth: 600, margin: '0 auto' }}>
        <h1 style={{ color: '#fff', fontFamily: 'monospace', marginBottom: 20, fontSize: 18 }}>
          Conversation Health Component Test
        </h1>

        <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
          {Object.keys(SCENARIOS).map((key) => (
            <button
              key={key}
              onClick={() => setScenario(key)}
              style={{
                padding: '6px 16px',
                borderRadius: 6,
                border: scenario === key ? '1px solid #00d4ff' : '1px solid #333',
                background: scenario === key ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: scenario === key ? '#00d4ff' : '#888',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'monospace',
              }}
            >
              {key}
            </button>
          ))}
        </div>

        <ConversationHealth health={SCENARIOS[scenario] ?? null} />
      </div>
    </div>
  );
}
