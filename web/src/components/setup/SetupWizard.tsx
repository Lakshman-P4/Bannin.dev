'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Copy, Check, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { api, ApiError } from '@/lib/api';

const STEPS = ['install', 'key', 'connect', 'confirm'] as const;
type Step = (typeof STEPS)[number];

const CONNECTION_POLL_INTERVAL = 2_000;

export function SetupWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('install');
  const [agentName, setAgentName] = useState('');
  const [agentId, setAgentId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');
  const copiedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (copiedTimeoutRef.current) clearTimeout(copiedTimeoutRef.current);
      if (failedTimeoutRef.current) clearTimeout(failedTimeoutRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll for agent connection when on the confirm step
  useEffect(() => {
    if (step !== 'confirm' || !agentId || isConnected) return;

    const checkConnection = async () => {
      try {
        const res = await api.agents.get(agentId);
        if (mountedRef.current && res.data.isOnline) {
          setIsConnected(true);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        // Agent not found or network error -- keep polling
      }
    };

    // Check immediately, then poll
    void checkConnection();
    pollRef.current = setInterval(checkConnection, CONNECTION_POLL_INTERVAL);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [step, agentId, isConnected]);

  const copyToClipboard = useCallback(async (text: string) => {
    setCopyFailed(false);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (copiedTimeoutRef.current) clearTimeout(copiedTimeoutRef.current);
      copiedTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyFailed(true);
      if (failedTimeoutRef.current) clearTimeout(failedTimeoutRef.current);
      failedTimeoutRef.current = setTimeout(() => setCopyFailed(false), 3000);
    }
  }, []);

  const createAgent = useCallback(async () => {
    if (!agentName.trim()) return;
    setIsCreating(true);
    setError('');
    try {
      const res = await api.agents.create({ name: agentName.trim() });
      setAgentId(res.data.id);
      setApiKey(res.data.apiKey);
      setStep('connect');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create agent');
    } finally {
      setIsCreating(false);
    }
  }, [agentName]);

  const stepIndex = STEPS.indexOf(step);

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div className="text-center">
        <h1 className="font-display text-2xl font-bold text-text-primary">
          Set up your first agent
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          This takes about two minutes. Let&apos;s get your machine connected.
        </p>
      </div>

      <div className="flex justify-center gap-2">
        {STEPS.map((s, i) => (
          <div
            key={s}
            className={`h-1.5 w-12 rounded-full ${
              i <= stepIndex ? 'bg-accent-cyan' : 'bg-surface-raised'
            }`}
            aria-hidden="true"
          />
        ))}
      </div>

      {step === 'install' && (
        <Card>
          <h2 className="font-display text-lg font-semibold text-text-primary mb-2">
            Step 1: Install the Agent
          </h2>
          <p className="text-sm text-text-secondary mb-4">
            Install Bannin on the machine you want to monitor.
          </p>
          <div className="flex items-center justify-between rounded-lg bg-surface-raised p-3">
            <code className="font-mono text-sm text-accent-cyan">pip install bannin</code>
            <button
              onClick={() => copyToClipboard('pip install bannin')}
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="Copy install command"
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>
          {copyFailed && (
            <p className="mt-2 text-xs text-status-amber">Copy failed. Select the text manually.</p>
          )}
          <p className="mt-3 text-xs text-text-muted">
            Windows: use <code className="text-text-secondary">python -m bannin.cli start</code>
          </p>
          <Button className="mt-4 w-full" onClick={() => setStep('key')}>
            Next
          </Button>
        </Card>
      )}

      {step === 'key' && (
        <Card>
          <h2 className="font-display text-lg font-semibold text-text-primary mb-2">
            Step 2: Create Your Agent
          </h2>
          <p className="text-sm text-text-secondary mb-4">
            Give your agent a name so you can identify it later.
          </p>
          <Input
            label="Agent name"
            placeholder="My Laptop"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            error={error}
          />
          <Button
            className="mt-4 w-full"
            onClick={createAgent}
            isLoading={isCreating}
            disabled={!agentName.trim()}
          >
            Create Agent
          </Button>
        </Card>
      )}

      {step === 'connect' && (
        <Card>
          <h2 className="font-display text-lg font-semibold text-text-primary mb-2">
            Step 3: Connect
          </h2>
          <p className="text-sm text-text-secondary mb-4">
            Save this API key -- you&apos;ll need it to connect.
          </p>
          <div className="flex items-center justify-between rounded-lg bg-surface-raised p-3 mb-4">
            <code className="font-mono text-xs text-accent-cyan break-all select-all">{apiKey}</code>
            <button
              onClick={() => copyToClipboard(apiKey)}
              className="ml-2 shrink-0 text-text-muted hover:text-text-primary transition-colors"
              aria-label="Copy API key"
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>
          {copyFailed && (
            <p className="mb-3 text-xs text-status-amber">Copy failed. Select the text manually.</p>
          )}
          <p className="text-sm text-text-secondary mb-2">Start the agent with your relay key:</p>
          <div className="rounded-lg bg-surface-raised p-3">
            <code className="font-mono text-xs text-accent-cyan break-all">
              python -m bannin.cli start --relay-key {apiKey}
            </code>
          </div>
          <p className="mt-2 text-xs text-text-muted">
            Or: <code className="text-text-secondary">bannin start --relay-key {apiKey.slice(0, 12)}...</code>
          </p>
          <Button className="mt-4 w-full" onClick={() => setStep('confirm')}>
            I&apos;ve started the agent
          </Button>
        </Card>
      )}

      {step === 'confirm' && (
        <Card className="text-center">
          {isConnected ? (
            <>
              <div className="mb-4 flex justify-center">
                <CheckCircle2 size={32} className="text-status-green" aria-hidden="true" />
              </div>
              <h2 className="font-display text-lg font-semibold text-text-primary mb-2">
                Agent connected
              </h2>
              <p className="text-sm text-text-secondary mb-4">
                Your agent &ldquo;{agentName}&rdquo; is online and sending data.
              </p>
              <Button onClick={() => router.push('/home')}>
                Go to Dashboard
              </Button>
            </>
          ) : (
            <>
              <div className="mb-4 flex justify-center">
                <Loader2 size={32} className="animate-spin text-accent-cyan" aria-hidden="true" />
              </div>
              <h2 className="font-display text-lg font-semibold text-text-primary mb-2">
                Waiting for connection...
              </h2>
              <p className="text-sm text-text-secondary mb-4">
                Make sure the agent is running with your API key. This page
                will update automatically when the agent connects.
              </p>
              <Button
                variant="secondary"
                className="mr-2"
                onClick={() => {
                  if (pollRef.current) {
                    clearInterval(pollRef.current);
                    pollRef.current = null;
                  }
                  setStep('connect');
                }}
              >
                Back
              </Button>
              <Button
                variant="ghost"
                onClick={() => router.push('/home')}
              >
                Skip to Dashboard
              </Button>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
