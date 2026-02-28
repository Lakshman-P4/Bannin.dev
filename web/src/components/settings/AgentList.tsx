'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Trash2, RefreshCw, Server, Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatRelativeTime } from '@/lib/utils';
import { api, ApiError } from '@/lib/api';
import type { Agent } from '@/types';

export function AgentList() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [newApiKey, setNewApiKey] = useState('');
  const [keyCopied, setKeyCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      const res = await api.agents.list();
      setAgents(res.data);
    } catch {
      setError('Failed to load agents.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await api.agents.delete(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      setConfirmDelete(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete agent.');
    }
  }, []);

  const handleRegenerate = useCallback(async (id: string) => {
    try {
      const res = await api.agents.regenerateKey(id);
      setNewApiKey(res.data.apiKey);
      setKeyCopied(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to regenerate key.');
    }
  }, []);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const copyApiKey = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(newApiKey);
      setKeyCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setKeyCopied(false), 2000);
    } catch {
      // Fallback: select the text for manual copy
      const el = document.querySelector<HTMLElement>('[data-api-key]');
      if (el) {
        const range = document.createRange();
        range.selectNodeContents(el);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
    }
  }, [newApiKey]);

  if (isLoading) {
    return (
      <Card>
        <p className="text-sm text-text-muted">Loading agents...</p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <h2 className="font-display text-lg font-semibold text-text-primary mb-4">
          Your Agents
        </h2>
        {error && (
          <p className="mb-3 text-sm text-status-red" role="alert">{error}</p>
        )}
        {agents.length === 0 ? (
          <p className="text-sm text-text-muted">No agents registered yet.</p>
        ) : (
          <ul className="space-y-3" aria-label="Agent list">
            {agents.map((agent) => (
              <li
                key={agent.id}
                className="flex items-center justify-between rounded-lg bg-surface-raised/50 p-3"
              >
                <div className="flex items-center gap-3">
                  <Server size={16} className="text-text-muted" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-medium text-text-primary">{agent.name}</p>
                    <p className="text-xs text-text-muted">
                      Last seen: {formatRelativeTime(agent.lastSeen)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={agent.isOnline ? 'success' : 'default'}>
                    {agent.isOnline ? 'Online' : 'Offline'}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRegenerate(agent.id)}
                    aria-label={`Regenerate API key for ${agent.name}`}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmDelete(agent.id)}
                    aria-label={`Delete ${agent.name}`}
                  >
                    <Trash2 size={14} className="text-status-red" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        isOpen={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="Delete Agent"
      >
        <p className="text-sm text-text-secondary mb-4">
          This will permanently delete the agent and all its data. This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmDelete(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => confirmDelete && handleDelete(confirmDelete)}
          >
            Delete
          </Button>
        </div>
      </Modal>

      <Modal
        isOpen={newApiKey !== ''}
        onClose={() => setNewApiKey('')}
        title="New API Key"
      >
        <p className="text-sm text-text-secondary mb-3">
          Save this key now. It will not be shown again.
        </p>
        <div className="flex items-center justify-between rounded-lg bg-surface-raised p-3">
          <code
            data-api-key
            className="font-mono text-xs text-accent-cyan break-all select-all"
          >
            {newApiKey}
          </code>
          <button
            onClick={copyApiKey}
            className="ml-2 shrink-0 text-text-muted hover:text-text-primary transition-colors"
            aria-label="Copy API key"
          >
            {keyCopied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={() => setNewApiKey('')}>Done</Button>
        </div>
      </Modal>
    </>
  );
}
