import { LoginForm } from '@/components/auth/LoginForm';

export const metadata = { title: 'Sign in -- Bannin' };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-display text-2xl font-bold text-text-primary">
            <span className="text-accent-cyan" aria-hidden="true">番</span> Sign in to Bannin
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            Monitor your compute from anywhere.
          </p>
        </div>
        <div className="glass-card p-6">
          <LoginForm />
        </div>
      </div>
    </main>
  );
}
