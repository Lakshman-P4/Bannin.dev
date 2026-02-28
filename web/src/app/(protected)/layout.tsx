'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { Navbar } from '@/components/shared/Navbar';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { Button } from '@/components/ui/Button';

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading, hasEmail, isEmailVerified, resendVerification, user } = useAuth();
  const router = useRouter();
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [bannerDismissed, setBannerDismissed] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  const handleResend = useCallback(async () => {
    setResendState('sending');
    try {
      await resendVerification();
      setResendState('sent');
    } catch {
      setResendState('error');
    }
  }, [resendVerification]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-accent-cyan border-t-transparent"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  // Show banner only when user has an email that is not yet verified
  const showBanner = hasEmail && !isEmailVerified && !bannerDismissed;

  const resendLabel =
    resendState === 'sending' ? 'Sending...' :
    resendState === 'sent' ? 'Sent' :
    resendState === 'error' ? 'Failed -- retry' :
    'Resend';

  return (
    <>
      <Navbar />
      {showBanner && (
        <div
          className="fixed top-14 left-0 right-0 z-30 border-b border-status-amber/20 bg-status-amber/5 px-4 py-2"
          role="status"
        >
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <p className="text-sm text-status-amber">
              Verify your email to enable password recovery and email alerts. Check your inbox at{' '}
              <strong>{user?.email}</strong>.
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResend}
                disabled={resendState === 'sending' || resendState === 'sent'}
              >
                {resendLabel}
              </Button>
              <button
                onClick={() => setBannerDismissed(true)}
                className="text-text-muted hover:text-text-secondary text-sm px-1"
                aria-label="Dismiss banner"
              >
                &times;
              </button>
            </div>
          </div>
        </div>
      )}
      <main className={`mx-auto max-w-7xl px-4 ${showBanner ? 'pt-28' : 'pt-20'} pb-12`}>
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </>
  );
}
