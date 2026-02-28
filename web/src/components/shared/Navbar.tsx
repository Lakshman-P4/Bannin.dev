'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Activity, Settings, LogOut, Menu, X } from 'lucide-react';
import { useState, useCallback } from 'react';
import { useAuth } from '@/components/auth/AuthProvider';
import { cn } from '@/lib/utils';
import { BanninEye } from './BanninEye';
import { ConnectionStatus } from './ConnectionStatus';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/events', label: 'Events', icon: Activity },
  { href: '/settings', label: 'Settings', icon: Settings },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleMobile = useCallback(() => setMobileOpen((prev) => !prev), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-40 border-b border-surface-border bg-surface/80 backdrop-blur-md"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <Link
          href="/home"
          className="flex items-center gap-2 font-display text-lg font-bold text-text-primary"
        >
          <BanninEye size={28} />
          <span>Bannin</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-surface-raised text-accent-cyan'
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-raised',
                )}
              >
                <Icon size={16} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <ConnectionStatus />
          {user && (
            <span className="text-xs text-text-muted truncate max-w-[120px]">
              {user.displayName}
            </span>
          )}
          <button
            onClick={logout}
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-text-secondary hover:text-status-red hover:bg-status-red/5 transition-colors"
            aria-label="Log out"
          >
            <LogOut size={16} aria-hidden="true" />
            <span className="sr-only md:not-sr-only">Logout</span>
          </button>
        </div>

        <button
          className="flex items-center md:hidden p-2 text-text-secondary hover:text-text-primary"
          onClick={toggleMobile}
          aria-expanded={mobileOpen}
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {mobileOpen && (
        <div className="border-t border-surface-border bg-surface-card px-4 py-3 md:hidden">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                onClick={closeMobile}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'text-accent-cyan bg-surface-raised'
                    : 'text-text-secondary hover:text-text-primary',
                )}
              >
                <Icon size={16} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
          <div className="mt-2 flex items-center justify-between border-t border-surface-border pt-3">
            <ConnectionStatus />
            <button
              onClick={logout}
              className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-status-red"
              aria-label="Log out"
            >
              <LogOut size={16} aria-hidden="true" />
              Logout
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
