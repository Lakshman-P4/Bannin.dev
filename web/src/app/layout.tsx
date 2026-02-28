import type { Metadata } from 'next';
import { Toaster } from 'sonner';
import { spaceGrotesk, dmSans, jetbrainsMono } from '@/lib/fonts';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { GrainOverlay } from '@/components/shared/GrainOverlay';
import './globals.css';

export const metadata: Metadata = {
  title: 'Bannin -- Watchman for Your Compute',
  description:
    'Monitor your machine, training runs, and AI tools from anywhere. OOM prediction, smart alerts, real-time dashboard.',
  icons: { icon: '/icon.png' },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-surface font-body text-text-primary antialiased">
        <AuthProvider>
          {children}
          <GrainOverlay />
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: '#0a0c10',
                border: '1px solid #141c28',
                color: '#e4ecf7',
                fontSize: '13px',
              },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
