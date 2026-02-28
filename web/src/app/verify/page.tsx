'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/components/auth/AuthProvider';

function VerifyContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshUser, resendVerification } = useAuth();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('No verification token found in URL.');
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        await api.auth.verify(token);
        if (cancelled) return;
        setStatus('success');
        setMessage('Email verified!');
        await refreshUser();
        setTimeout(() => {
          if (!cancelled) router.push('/home');
        }, 2000);
      } catch (err) {
        if (cancelled) return;
        setStatus('error');
        setMessage(
          err instanceof ApiError
            ? err.message
            : 'Verification failed. The link may have expired.',
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, refreshUser, router]);

  const handleResend = async () => {
    setResending(true);
    try {
      await resendVerification();
      setMessage('Verification email resent. Check your inbox.');
    } catch {
      setMessage('Failed to resend. Please try again.');
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="glass-card w-full max-w-sm p-8 text-center">
      {status === 'loading' && (
        <>
          <Loader2 size={32} className="mx-auto mb-4 animate-spin text-accent-cyan" aria-hidden="true" />
          <p className="text-sm text-text-secondary">Verifying your email...</p>
        </>
      )}
      {status === 'success' && (
        <>
          <CheckCircle size={32} className="mx-auto mb-4 text-status-green" aria-hidden="true" />
          <h1 className="font-display text-xl font-bold text-text-primary mb-2">{message}</h1>
          <p className="text-sm text-text-secondary">Redirecting to dashboard...</p>
        </>
      )}
      {status === 'error' && (
        <>
          <XCircle size={32} className="mx-auto mb-4 text-status-red" aria-hidden="true" />
          <h1 className="font-display text-xl font-bold text-text-primary mb-2">
            Verification failed
          </h1>
          <p className="text-sm text-text-secondary mb-4">{message}</p>
          <Button variant="secondary" onClick={handleResend} isLoading={resending}>
            Resend verification email
          </Button>
        </>
      )}
    </div>
  );
}

export default function VerifyPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Suspense
        fallback={
          <div className="glass-card w-full max-w-sm p-8 text-center">
            <Loader2 size={32} className="mx-auto mb-4 animate-spin text-accent-cyan" aria-hidden="true" />
            <p className="text-sm text-text-secondary">Loading...</p>
          </div>
        }
      >
        <VerifyContent />
      </Suspense>
    </main>
  );
}
