import { z } from "zod";
import { USERNAME_MIN_LENGTH, USERNAME_MAX_LENGTH } from "../constants.js";

const usernameRegex = /^[a-z0-9_]+$/;

export const registerSchema = z.object({
  username: z
    .string()
    .min(USERNAME_MIN_LENGTH, `Username must be at least ${USERNAME_MIN_LENGTH} characters`)
    .max(USERNAME_MAX_LENGTH, `Username must be at most ${USERNAME_MAX_LENGTH} characters`)
    .transform((s) => s.toLowerCase().trim())
    .pipe(z.string().regex(usernameRegex, "Username may only contain lowercase letters, numbers, and underscores")),
  password: z.string().min(8, "Password must be at least 8 characters").max(128),
  displayName: z.string().min(1, "Display name is required").max(100),
  email: z.string().email("Invalid email address").max(255).optional(),
});

export const loginSchema = z.object({
  identifier: z
    .string()
    .min(1, "Username or email is required")
    .max(320)
    .transform((s) => s.toLowerCase().trim()),
  password: z.string().min(1, "Password is required").max(128),
});

export const refreshSchema = z.object({
  refreshToken: z.string().min(1, "Refresh token is required"),
});

export const updateProfileSchema = z.object({
  displayName: z.string().min(1).max(100).optional(),
  email: z.string().email("Invalid email address").max(255).nullable().optional(),
});

export const changePasswordSchema = z.object({
  currentPassword: z.string().min(1, "Current password is required"),
  newPassword: z.string().min(8, "New password must be at least 8 characters").max(128),
});

export const deleteAccountSchema = z.object({
  password: z.string().min(1, "Password is required for account deletion"),
});

export const forgotPasswordSchema = z.object({
  email: z.string().email("Invalid email address"),
});

export const resetPasswordSchema = z.object({
  token: z.string().min(1, "Reset token is required"),
  newPassword: z.string().min(8, "Password must be at least 8 characters").max(128),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type RefreshInput = z.infer<typeof refreshSchema>;
export type UpdateProfileInput = z.infer<typeof updateProfileSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
export type DeleteAccountInput = z.infer<typeof deleteAccountSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
