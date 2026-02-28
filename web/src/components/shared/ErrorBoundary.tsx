'use client';

import { Component, type ReactNode, type ErrorInfo } from 'react';
import { Button } from '@/components/ui/Button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center py-24 text-center px-4">
          <h2 className="font-display text-xl font-bold text-text-primary mb-2">
            Something went wrong
          </h2>
          <p className="text-sm text-text-secondary mb-4 max-w-md">
            An unexpected error occurred. Try refreshing the page.
          </p>
          <Button onClick={this.handleReset}>Try again</Button>
        </div>
      );
    }

    return this.props.children;
  }
}
