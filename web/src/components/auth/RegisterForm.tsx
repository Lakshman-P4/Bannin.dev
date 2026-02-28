'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { registerSchema, type RegisterFormData } from '@/schemas/auth';
import { useAuth } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ApiError } from '@/lib/api';

export function RegisterForm() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    setServerError('');
    try {
      const email = data.email && data.email.length > 0 ? data.email : undefined;
      await registerUser(data.username, data.displayName, data.password, email);
      router.push('/setup');
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
        label="Username"
        type="text"
        autoComplete="username"
        placeholder="your_username"
        error={errors.username?.message}
        {...register('username')}
      />

      <Input
        label="Display name"
        type="text"
        autoComplete="name"
        placeholder="How you want to appear"
        error={errors.displayName?.message}
        {...register('displayName')}
      />

      <Input
        label="Password"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
        error={errors.password?.message}
        {...register('password')}
      />

      <div>
        <Input
          label="Email (optional)"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register('email')}
        />
        <p className="mt-1 text-xs text-text-muted">
          For account recovery and alert notifications. You can add this later.
        </p>
      </div>

      <Button type="submit" isLoading={isSubmitting} className="w-full">
        Create account
      </Button>

      <p className="text-center text-sm text-text-secondary">
        Already have an account?{' '}
        <Link href="/login" className="text-accent-cyan hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
