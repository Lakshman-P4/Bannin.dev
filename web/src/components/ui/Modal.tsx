'use client';

import { useEffect, useRef, useCallback, useId, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}

export function Modal({ isOpen, onClose, title, children, className }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      dialogRef.current?.showModal();
      document.addEventListener('keydown', handleKeyDown);

      const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(
        'button, input, [tabindex="0"], a[href]',
      );
      firstFocusable?.focus();
    } else {
      dialogRef.current?.close();
      previousFocusRef.current?.focus();
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-0 h-full w-full bg-transparent p-0 backdrop:bg-black/60"
      aria-labelledby={titleId}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className={cn(
            'glass-card w-full max-w-md p-6 animate-fade-up',
            className,
          )}
          role="document"
        >
          <h2
            id={titleId}
            className="font-display text-lg font-semibold text-text-primary mb-4"
          >
            {title}
          </h2>
          {children}
        </div>
      </div>
    </dialog>
  );
}
