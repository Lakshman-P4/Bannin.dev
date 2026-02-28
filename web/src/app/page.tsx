import { Hero } from '@/components/landing/Hero';
import { ProblemSolution } from '@/components/landing/ProblemSolution';
import { Nightmares } from '@/components/landing/Nightmares';
import { Features } from '@/components/landing/Features';
import { ProofStats } from '@/components/landing/ProofStats';
import { SetupPreview } from '@/components/landing/SetupPreview';
import { Footer } from '@/components/landing/Footer';

export default function LandingPage() {
  return (
    <main>
      <Hero />
      <ProblemSolution />
      <Nightmares />
      <Features />
      <ProofStats />
      <SetupPreview />
      <Footer />
    </main>
  );
}
