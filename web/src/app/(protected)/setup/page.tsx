import { AnimatedPage } from '@/components/shared/AnimatedPage';
import { SetupWizard } from '@/components/setup/SetupWizard';

export default function SetupPage() {
  return (
    <AnimatedPage className="py-8">
      <SetupWizard />
    </AnimatedPage>
  );
}
