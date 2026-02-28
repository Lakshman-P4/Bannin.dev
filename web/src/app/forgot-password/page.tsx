'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { forgotPasswordSchema, type ForgotPasswordFormData } from '@/schemas/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { api, ApiError } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [serverError, setServerError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setServerError('');
    try {
      await api.auth.forgotPassword(data.email);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError('Something went wrong. Please try again.');
      }
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="glass-card w-full max-w-sm p-8">
        {sent ? (
          <div className="text-center">
            <CheckCircle size={32} className="mx-auto mb-4 text-status-green" aria-hidden="true" />
            <h1 className="font-display text-xl font-bold text-text-primary mb-2">
              Check your inbox
            </h1>
            <p className="text-sm text-text-secondary mb-6">
              If an account with that email exists, we sent a password reset link.
            </p>
            <Link href="/login" className="text-sm text-accent-cyan hover:underline">
              Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <div className="text-center mb-6">
              <Mail size={32} className="mx-auto mb-4 text-accent-cyan" aria-hidden="true" />
              <h1 className="font-display text-xl font-bold text-text-primary mb-2">
                Reset your password
              </h1>
              <p className="text-sm text-text-secondary">
                Enter the email address linked to your account. If you didn&apos;t add an email, you&apos;ll need to create a new account.
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
                label="Email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                error={errors.email?.message}
                {...register('email')}
              />

              <Button type="submit" isLoading={isSubmitting} className="w-full">
                Send reset link
              </Button>
            </form>

            <div className="mt-4 text-center">
              <Link href="/login" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-accent-cyan">
                <ArrowLeft size={14} aria-hidden="true" />
                Back to sign in
              </Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
