import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-surface-border py-10 px-4">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="text-accent-cyan font-display text-lg" aria-hidden="true">
            番人
          </span>
          <span className="text-sm text-text-muted">
            Bannin -- watchman for your compute.
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm text-text-muted">
          <Link href="/login" className="hover:text-text-secondary transition-colors">
            Sign in
          </Link>
          <a
            href="https://github.com/Lakshman-P4/Bannin.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-secondary transition-colors"
          >
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
