import type { Metadata } from 'next';
import { Newsreader, Geist, Geist_Mono } from 'next/font/google';
import { PageTransition } from '@/components/motion/PageTransition';
import './globals.css';

const serif = Newsreader({ subsets: ['latin'], variable: '--font-serif', display: 'swap' });
const sans = Geist({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });
const mono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' });

export const metadata: Metadata = {
  title: 'DVI — semantic data-change detection',
  description: 'Catch the silent data change that passes every structural check.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body className="font-sans">
        <PageTransition>{children}</PageTransition>
      </body>
    </html>
  );
}
