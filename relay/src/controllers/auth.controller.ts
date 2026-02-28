import type { Request, Response, NextFunction } from "express";
import * as authService from "../services/auth.service.js";
import { sendVerificationEmail, sendPasswordResetEmail } from "../services/email.service.js";
import type {
  RegisterInput,
  LoginInput,
  RefreshInput,
  UpdateProfileInput,
  ChangePasswordInput,
  DeleteAccountInput,
  ForgotPasswordInput,
  ResetPasswordInput,
} from "../schemas/auth.schema.js";

export async function register(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as RegisterInput;
    const result = await authService.register(input);

    // Send verification email if email was provided (non-blocking)
    if (input.email && result.verifyToken) {
      sendVerificationEmail(input.email, result.verifyToken).catch(() => {});
    }

    res.status(201).json({
      data: {
        user: result.user,
        accessToken: result.tokens.accessToken,
        refreshToken: result.tokens.refreshToken,
      },
    });
  } catch (err) {
    if (err instanceof authService.ConflictError) {
      res.status(409).json({ error: { code: "CONFLICT", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function login(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as LoginInput;
    const result = await authService.login(input);

    res.json({
      data: {
        user: result.user,
        accessToken: result.tokens.accessToken,
        refreshToken: result.tokens.refreshToken,
      },
    });
  } catch (err) {
    if (err instanceof authService.AuthError) {
      res.status(401).json({ error: { code: "INVALID_CREDENTIALS", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function verifyEmail(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const raw = req.params["token"];
    const token = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
    if (!token) {
      res.status(400).json({ error: { code: "BAD_REQUEST", message: "Token is required" } });
      return;
    }
    const result = await authService.verifyEmail(token);
    res.json({ data: { message: "Email verified successfully", email: result.email } });
  } catch (err) {
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    if (err instanceof authService.AuthError) {
      res.status(400).json({ error: { code: "TOKEN_EXPIRED", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function resendVerification(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const result = await authService.resendVerification(req.user!.id);
    sendVerificationEmail(result.email, result.verifyToken).catch(() => {});
    res.json({ data: { message: "Verification email sent" } });
  } catch (err) {
    if (err instanceof authService.ConflictError) {
      res.status(409).json({ error: { code: "ALREADY_VERIFIED", message: err.message } });
      return;
    }
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function refresh(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const { refreshToken } = req.body as RefreshInput;
    const tokens = await authService.refreshTokens(refreshToken);
    res.json({ data: tokens });
  } catch (err) {
    if (err instanceof authService.AuthError) {
      res.status(401).json({ error: { code: "INVALID_TOKEN", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function me(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const user = await authService.getMe(req.user!.id);
    res.json({ data: user });
  } catch (err) {
    next(err);
  }
}

export async function updateProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as UpdateProfileInput;
    const result = await authService.updateProfile(req.user!.id, input);

    // If email changed, send verification to new email (non-blocking)
    if (result.verifyToken && result.user.email) {
      sendVerificationEmail(result.user.email, result.verifyToken).catch(() => {});
    }

    res.json({ data: result.user });
  } catch (err) {
    if (err instanceof authService.ConflictError) {
      res.status(409).json({ error: { code: "CONFLICT", message: err.message } });
      return;
    }
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function changePassword(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as ChangePasswordInput;
    await authService.changePassword(req.user!.id, input);
    res.json({ data: { message: "Password changed successfully" } });
  } catch (err) {
    if (err instanceof authService.AuthError) {
      res.status(401).json({ error: { code: "INVALID_PASSWORD", message: err.message } });
      return;
    }
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function deleteAccount(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as DeleteAccountInput;
    await authService.deleteAccount(req.user!.id, input);
    res.json({ data: { message: "Account deleted" } });
  } catch (err) {
    if (err instanceof authService.AuthError) {
      res.status(401).json({ error: { code: "INVALID_PASSWORD", message: err.message } });
      return;
    }
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "NOT_FOUND", message: err.message } });
      return;
    }
    next(err);
  }
}

export async function forgotPassword(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as ForgotPasswordInput;
    await authService.forgotPassword(input);

    // Attempt to get the token and send email (non-blocking, don't reveal existence)
    const token = await authService.getForgotPasswordToken(input.email);
    if (token) {
      sendPasswordResetEmail(input.email, token).catch(() => {});
    }

    // Always return 200 regardless of whether email exists
    res.json({ data: { message: "If an account with that email exists, a reset link has been sent" } });
  } catch (err) {
    next(err);
  }
}

export async function resetPassword(req: Request, res: Response, next: NextFunction): Promise<void> {
  try {
    const input = req.body as ResetPasswordInput;
    await authService.resetPassword(input);
    res.json({ data: { message: "Password reset successfully" } });
  } catch (err) {
    if (err instanceof authService.NotFoundError) {
      res.status(404).json({ error: { code: "INVALID_TOKEN", message: err.message } });
      return;
    }
    if (err instanceof authService.AuthError) {
      res.status(400).json({ error: { code: "TOKEN_EXPIRED", message: err.message } });
      return;
    }
    next(err);
  }
}
