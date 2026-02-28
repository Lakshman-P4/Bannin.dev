import { RegisterForm } from '@/components/auth/RegisterForm';

export const metadata = { title: 'Create account -- Bannin' };

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-display text-2xl font-bold text-text-primary">
            <span className="text-accent-cyan" aria-hidden="true">番</span> Create your account
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            Start monitoring in two minutes.
          </p>
        </div>
        <div className="glass-card p-6">
          <RegisterForm />
        </div>
      </div>
    </main>
  );
}
