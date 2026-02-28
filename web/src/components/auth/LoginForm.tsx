'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { loginSchema, type LoginFormData } from '@/schemas/auth';
import { useAuth } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ApiError } from '@/lib/api';

export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setServerError('');
    try {
      await login(data.identifier, data.password);
      router.push('/home');
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError('Something went wrong. Please try again.');
      }
    }
  };

  return (
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
        label="Username or email"
        type="text"
        autoComplete="username"
        placeholder="your_username or you@example.com"
        error={errors.identifier?.message}
        {...register('identifier')}
      />

      <Input
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="Your password"
        error={errors.password?.message}
        {...register('password')}
      />

      <Button type="submit" isLoading={isSubmitting} className="w-full">
        Sign in
      </Button>

      <div className="text-center text-sm text-text-secondary space-y-1">
        <p>
          No account yet?{' '}
          <Link href="/register" className="text-accent-cyan hover:underline">
            Create one
          </Link>
        </p>
        <p>
          <Link href="/forgot-password" className="text-text-secondary hover:text-accent-cyan hover:underline">
            Forgot password?
          </Link>
        </p>
      </div>
    </form>
  );
}
