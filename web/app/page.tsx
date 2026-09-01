import { Hero } from '@/components/landing/Hero';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { SignatureShowcase } from '@/components/landing/SignatureShowcase';
import { Proof } from '@/components/landing/Proof';
import { FooterCta } from '@/components/landing/FooterCta';

export default function Home() {
  return (
    <main>
      <Hero />
      <HowItWorks />
      <SignatureShowcase />
      <Proof />
      <FooterCta />
    </main>
  );
}
