'use client';

import { useState, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuth } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { api, ApiError } from '@/lib/api';
import { changePasswordSchema, type ChangePasswordFormData } from '@/schemas/auth';

export function AccountSettings() {
  const { user, logout, refreshUser, hasEmail, isEmailVerified, resendVerification } = useAuth();

  // Display name editing
  const [editingName, setEditingName] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [nameLoading, setNameLoading] = useState(false);
  const [nameError, setNameError] = useState('');

  // Email management
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailValue, setEmailValue] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [resendingVerification, setResendingVerification] = useState(false);

  // Password change
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

  // Delete account
  const [showDelete, setShowDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const passwordForm = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  });

  const handleUpdateName = useCallback(async () => {
    if (!displayName.trim()) return;
    setNameLoading(true);
    setNameError('');
    try {
      await api.auth.updateProfile({ displayName: displayName.trim() });
      await refreshUser();
      setEditingName(false);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : 'Failed to update name.');
    } finally {
      setNameLoading(false);
    }
  }, [displayName, refreshUser]);

  const handleUpdateEmail = useCallback(async () => {
    setEmailLoading(true);
    setEmailError('');
    setEmailSuccess('');
    try {
      const email = emailValue.trim() || null;
      await api.auth.updateProfile({ email });
      await refreshUser();
      setEditingEmail(false);
      if (email) {
        setEmailSuccess('Verification email sent to your new address.');
      }
    } catch (err) {
      setEmailError(err instanceof ApiError ? err.message : 'Failed to update email.');
    } finally {
      setEmailLoading(false);
    }
  }, [emailValue, refreshUser]);

  const handleResendVerification = useCallback(async () => {
    setResendingVerification(true);
    try {
      await resendVerification();
      setEmailSuccess('Verification email resent.');
    } catch {
      setEmailError('Failed to resend verification email.');
    } finally {
      setResendingVerification(false);
    }
  }, [resendVerification]);

  const handleChangePassword = useCallback(async (data: ChangePasswordFormData) => {
    setPasswordError('');
    setPasswordSuccess('');
    try {
      await api.auth.changePassword(data);
      setPasswordSuccess('Password changed.');
      setShowPasswordForm(false);
      passwordForm.reset();
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : 'Failed to change password.');
    }
  }, [passwordForm]);

  const handleDeleteAccount = useCallback(async () => {
    if (!deletePassword) return;
    setIsDeleting(true);
    setDeleteError('');
    try {
      await api.auth.deleteAccount(deletePassword);
      logout();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : 'Failed to delete account.');
    } finally {
      setIsDeleting(false);
    }
  }, [deletePassword, logout]);

  if (!user) return null;

  return (
    <>
      <Card>
        <h2 className="font-display text-lg font-semibold text-text-primary mb-4">Account</h2>
        <div className="space-y-4">
          {/* Username (read-only) */}
          <div>
            <p className="text-xs text-text-muted">Username</p>
            <p className="text-sm text-text-primary font-mono">@{user.username}</p>
          </div>

          {/* Display name */}
          <div>
            <p className="text-xs text-text-muted">Display name</p>
            {editingName ? (
              <div className="flex items-center gap-2 mt-1">
                <Input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your display name"
                  className="flex-1"
                />
                <Button size="sm" onClick={handleUpdateName} isLoading={nameLoading}>Save</Button>
                <Button size="sm" variant="secondary" onClick={() => setEditingName(false)}>Cancel</Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <p className="text-sm text-text-primary">{user.displayName}</p>
                <button
                  onClick={() => { setDisplayName(user.displayName); setEditingName(true); }}
                  className="text-xs text-accent-cyan hover:underline"
                >
                  Edit
                </button>
              </div>
            )}
            {nameError && <p className="text-xs text-status-red mt-1">{nameError}</p>}
          </div>

          {/* Email */}
          <div>
            <p className="text-xs text-text-muted">Email</p>
            {editingEmail ? (
              <div className="mt-1">
                <div className="flex items-center gap-2">
                  <Input
                    type="email"
                    value={emailValue}
                    onChange={(e) => setEmailValue(e.target.value)}
                    placeholder="you@example.com (leave empty to remove)"
                    className="flex-1"
                  />
                  <Button size="sm" onClick={handleUpdateEmail} isLoading={emailLoading}>Save</Button>
                  <Button size="sm" variant="secondary" onClick={() => setEditingEmail(false)}>Cancel</Button>
                </div>
                {emailError && <p className="text-xs text-status-red mt-1">{emailError}</p>}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {user.email ? (
                  <>
                    <p className="text-sm text-text-primary">{user.email}</p>
                    {isEmailVerified ? (
                      <span className="text-xs text-status-green">Verified</span>
                    ) : (
                      <span className="text-xs text-status-amber">Unverified</span>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-text-muted">No email added</p>
                )}
                <button
                  onClick={() => { setEmailValue(user.email ?? ''); setEditingEmail(true); setEmailError(''); setEmailSuccess(''); }}
                  className="text-xs text-accent-cyan hover:underline"
                >
                  {user.email ? 'Change' : 'Add email'}
                </button>
                {hasEmail && !isEmailVerified && (
                  <button
                    onClick={handleResendVerification}
                    disabled={resendingVerification}
                    className="text-xs text-accent-cyan hover:underline disabled:opacity-50"
                  >
                    {resendingVerification ? 'Sending...' : 'Resend verification'}
                  </button>
                )}
              </div>
            )}
            {emailSuccess && <p className="text-xs text-status-green mt-1">{emailSuccess}</p>}
            {!editingEmail && !user.email && (
              <p className="text-xs text-text-muted mt-1">
                Add your email to enable password recovery and email alerts.
              </p>
            )}
          </div>

          {/* Password */}
          <div>
            <p className="text-xs text-text-muted">Password</p>
            {showPasswordForm ? (
              <form onSubmit={passwordForm.handleSubmit(handleChangePassword)} className="mt-2 space-y-3">
                <Input
                  type="password"
                  label="Current password"
                  autoComplete="current-password"
                  error={passwordForm.formState.errors.currentPassword?.message}
                  {...passwordForm.register('currentPassword')}
                />
                <Input
                  type="password"
                  label="New password"
                  autoComplete="new-password"
                  error={passwordForm.formState.errors.newPassword?.message}
                  {...passwordForm.register('newPassword')}
                />
                {passwordError && <p className="text-xs text-status-red">{passwordError}</p>}
                <div className="flex gap-2">
                  <Button type="submit" size="sm" isLoading={passwordForm.formState.isSubmitting}>Change password</Button>
                  <Button type="button" size="sm" variant="secondary" onClick={() => { setShowPasswordForm(false); passwordForm.reset(); setPasswordError(''); }}>Cancel</Button>
                </div>
              </form>
            ) : (
              <div className="flex items-center gap-2 mt-1">
                <p className="text-sm text-text-secondary">********</p>
                <button onClick={() => setShowPasswordForm(true)} className="text-xs text-accent-cyan hover:underline">
                  Change
                </button>
              </div>
            )}
            {passwordSuccess && <p className="text-xs text-status-green mt-1">{passwordSuccess}</p>}
          </div>
        </div>

        <div className="mt-6 border-t border-surface-border pt-4">
          <Button variant="danger" size="sm" onClick={() => setShowDelete(true)}>
            Delete account
          </Button>
        </div>
      </Card>

      <Modal
        isOpen={showDelete}
        onClose={() => {
          setShowDelete(false);
          setDeletePassword('');
          setDeleteError('');
        }}
        title="Delete Account"
      >
        <p className="text-sm text-text-secondary mb-4">
          This will permanently delete your account and all associated data.
          Enter your password to confirm.
        </p>
        {deleteError && (
          <p className="mb-3 text-sm text-status-red" role="alert">{deleteError}</p>
        )}
        <Input
          type="password"
          value={deletePassword}
          onChange={(e) => setDeletePassword(e.target.value)}
          placeholder="Your password"
          autoComplete="current-password"
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setShowDelete(false);
              setDeletePassword('');
              setDeleteError('');
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={!deletePassword || isDeleting}
            isLoading={isDeleting}
            onClick={handleDeleteAccount}
          >
            Delete my account
          </Button>
        </div>
      </Modal>
    </>
  );
}
