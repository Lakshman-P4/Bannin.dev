import { AnimatedPage } from '@/components/shared/AnimatedPage';
import { NotificationSettings } from '@/components/settings/NotificationSettings';
import { AgentList } from '@/components/settings/AgentList';
import { AccountSettings } from '@/components/settings/AccountSettings';

export default function SettingsPage() {
  return (
    <AnimatedPage>
      <h1 className="font-display text-2xl font-bold text-text-primary mb-6">Settings</h1>
      <div className="space-y-6">
        <NotificationSettings />
        <AgentList />
        <AccountSettings />
      </div>
    </AnimatedPage>
  );
}
