import { getIncident, getIncidents } from '@/lib/data';
import { Hero } from '@/components/landing/Hero';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { SignatureShowcase } from '@/components/landing/SignatureShowcase';
import { Proof } from '@/components/landing/Proof';
import { FooterCta } from '@/components/landing/FooterCta';

export default async function Home() {
  const items = await getIncidents();
  const specimen = items.length > 0 ? await getIncident(items[0].id) : null;

  return (
    <main>
      <Hero specimen={specimen} />
      <HowItWorks />
      <SignatureShowcase />
      <Proof />
      <FooterCta />
    </main>
  );
}
