'use client';

import { Suspense, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Lock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { resetPasswordSchema, type ResetPasswordFormData } from '@/schemas/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { api, ApiError } from '@/lib/api';

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'form' | 'success' | 'error'>(!token ? 'error' : 'form');
  const [serverError, setServerError] = useState(!token ? 'No reset token found in URL.' : '');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) return;
    setServerError('');
    try {
      await api.auth.resetPassword(token, data.newPassword);
      setStatus('success');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404 || err.code === 'TOKEN_EXPIRED') {
          setStatus('error');
          setServerError(err.message);
        } else {
          setServerError(err.message);
        }
      } else {
        setServerError('Something went wrong. Please try again.');
      }
    }
  };

  if (status === 'success') {
    return (
      <div className="glass-card w-full max-w-sm p-8 text-center">
        <CheckCircle size={32} className="mx-auto mb-4 text-status-green" aria-hidden="true" />
        <h1 className="font-display text-xl font-bold text-text-primary mb-2">
          Password reset
        </h1>
        <p className="text-sm text-text-secondary mb-6">
          Your password has been updated. You can now sign in with your new password.
        </p>
        <Link href="/login">
          <Button className="w-full">Sign in</Button>
        </Link>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="glass-card w-full max-w-sm p-8 text-center">
        <XCircle size={32} className="mx-auto mb-4 text-status-red" aria-hidden="true" />
        <h1 className="font-display text-xl font-bold text-text-primary mb-2">
          Reset failed
        </h1>
        <p className="text-sm text-text-secondary mb-6">{serverError}</p>
        <Link href="/forgot-password">
          <Button variant="secondary" className="w-full">Request a new link</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="glass-card w-full max-w-sm p-8">
      <div className="text-center mb-6">
        <Lock size={32} className="mx-auto mb-4 text-accent-cyan" aria-hidden="true" />
        <h1 className="font-display text-xl font-bold text-text-primary mb-2">
          Set new password
        </h1>
        <p className="text-sm text-text-secondary">
          Choose a new password for your account.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {serverError && (
          <div
            className="rounded-lg border border-status-red/20 bg-status-red/5 p-3 text-sm text-status-red"
            role="alert"
          >
            {serverError}
          </div>
        )}

        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          error={errors.newPassword?.message}
          {...register('newPassword')}
        />

        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Reset password
        </Button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
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
        <ResetPasswordContent />
      </Suspense>
    </main>
  );
}
