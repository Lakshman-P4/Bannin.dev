'use client';

import { useState, useCallback, useEffect } from 'react';
import { Bell, BellOff } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api } from '@/lib/api';

const isPushSupported =
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'Notification' in window &&
  'PushManager' in window;

export function NotificationSettings() {
  const [enabled, setEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isChecking, setIsChecking] = useState(isPushSupported);
  const [status, setStatus] = useState('');

  // Sync enabled state from actual browser push subscription on mount.
  // navigator.serviceWorker.ready hangs if no service worker is registered,
  // so check registrations first and bail out with a timeout fallback.
  useEffect(() => {
    if (!isPushSupported) return;

    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled) setIsChecking(false);
    }, 3_000);

    navigator.serviceWorker.getRegistrations()
      .then((regs) => {
        if (cancelled) return;
        if (regs.length === 0) {
          // No service worker registered -- push not set up yet
          setIsChecking(false);
          return;
        }
        return navigator.serviceWorker.ready
          .then((reg) => reg.pushManager.getSubscription())
          .then((sub) => { if (!cancelled) setEnabled(sub !== null); });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsChecking(false);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, []);

  const togglePush = useCallback(async () => {
    setIsLoading(true);
    setStatus('');

    try {
      if (enabled) {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await api.notifications.unsubscribePush(sub.endpoint);
          await sub.unsubscribe();
        }
        setEnabled(false);
        setStatus('Push notifications disabled.');
      } else {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          setStatus('Permission denied. Check your browser settings.');
          return;
        }
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY,
        });
        await api.notifications.subscribePush(sub.toJSON());
        setEnabled(true);
        setStatus('Push notifications enabled.');
      }
    } catch {
      setStatus('Failed to update notifications.');
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  const testNotification = useCallback(async () => {
    try {
      await api.notifications.test();
      setStatus('Test notification sent.');
    } catch {
      setStatus('Failed to send test notification.');
    }
  }, []);

  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-text-primary mb-4">
        Notifications
      </h2>
      {!isPushSupported ? (
        <p className="text-sm text-text-muted">
          Push notifications are not supported in this browser.
        </p>
      ) : isChecking ? (
        <p className="text-sm text-text-muted">Checking notification status...</p>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {enabled ? (
                <Bell size={20} className="text-accent-cyan" aria-hidden="true" />
              ) : (
                <BellOff size={20} className="text-text-muted" aria-hidden="true" />
              )}
              <div>
                <p className="text-sm text-text-primary">Browser push notifications</p>
                <p className="text-xs text-text-muted">Get alerted for critical events</p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={togglePush}
              isLoading={isLoading}
            >
              {enabled ? 'Disable' : 'Enable'}
            </Button>
          </div>
          {enabled && (
            <div className="mt-4">
              <Button variant="ghost" size="sm" onClick={testNotification}>
                Send test notification
              </Button>
            </div>
          )}
        </>
      )}
      {status && (
        <p className="mt-3 text-xs text-text-secondary" role="status" aria-live="polite">
          {status}
        </p>
      )}
    </Card>
  );
}
