import nodemailer from "nodemailer";
import type { Transporter } from "nodemailer";
import { getEnv } from "../config/env.js";
import { logger } from "../lib/logger.js";

let _transporter: Transporter | null = null;
let _transporterReady: Promise<Transporter | null> | null = null;

function initTransporter(): Promise<Transporter | null> {
  if (_transporterReady) return _transporterReady;

  _transporterReady = (async () => {
    if (_transporter) return _transporter;

    const env = getEnv();
    const hasRealSmtp =
      env.SMTP_HOST &&
      env.SMTP_USER &&
      env.SMTP_USER !== "your@email.com";

    if (hasRealSmtp) {
      _transporter = nodemailer.createTransport({
        host: env.SMTP_HOST,
        port: env.SMTP_PORT,
        secure: env.SMTP_PORT === 465,
        auth: {
          user: env.SMTP_USER,
          pass: env.SMTP_PASS,
        },
      });
      logger.info("SMTP configured with real credentials");
      return _transporter;
    }

    // Development fallback: auto-create Ethereal test account
    if (env.NODE_ENV !== "production") {
      try {
        const testAccount = await nodemailer.createTestAccount();
        _transporter = nodemailer.createTransport({
          host: "smtp.ethereal.email",
          port: 587,
          secure: false,
          auth: {
            user: testAccount.user,
            pass: testAccount.pass,
          },
        });
        logger.info(
          { user: testAccount.user },
          "Ethereal dev email account created -- emails viewable at https://ethereal.email/login",
        );
        return _transporter;
      } catch (err) {
        logger.warn({ err }, "Failed to create Ethereal account, email disabled");
        return null;
      }
    }

    logger.warn("SMTP not configured, email sending disabled");
    return null;
  })();

  return _transporterReady;
}

export async function sendVerificationEmail(to: string, token: string): Promise<void> {
  const env = getEnv();
  const transporter = await initTransporter();
  if (!transporter) {
    logger.info({ to }, "Verification email skipped (no transport available)");
    return;
  }

  const verifyUrl = `${env.APP_URL}/verify?token=${token}`;

  const html = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#12121a;border-radius:12px;border:1px solid #1e1e2e;padding:40px;">
    <h1 style="color:#00e5ff;font-size:24px;margin:0 0 8px;">Bannin</h1>
    <p style="color:#a0a0b0;font-size:14px;margin:0 0 24px;">&#30058;&#20154; -- Your AI Watchman</p>
    <p style="color:#e0e0e0;font-size:16px;line-height:1.6;margin:0 0 24px;">
      Click below to verify your email address.
    </p>
    <a href="${verifyUrl}" style="display:inline-block;background:#00e5ff;color:#0a0a0f;font-weight:600;font-size:14px;padding:12px 28px;border-radius:8px;text-decoration:none;">
      Verify Email
    </a>
    <p style="color:#606070;font-size:12px;margin:24px 0 0;">
      If you didn't request this, you can safely ignore this email.
    </p>
  </div>
</body>
</html>`;

  const text = `Bannin -- Verify your email\n\nVerify your email: ${verifyUrl}\n\nIf you didn't request this, ignore this email.`;

  try {
    const info = await transporter.sendMail({
      from: env.SMTP_FROM,
      to,
      subject: "Verify your Bannin email",
      html,
      text,
    });
    logger.info({ to }, "Verification email sent");

    const previewUrl = nodemailer.getTestMessageUrl(info);
    if (previewUrl) {
      logger.info({ previewUrl }, "View verification email at this URL");
    }
  } catch (err) {
    logger.error({ err, to }, "Failed to send verification email");
    throw new Error("Failed to send verification email");
  }
}

export async function sendPasswordResetEmail(to: string, token: string): Promise<void> {
  const env = getEnv();
  const transporter = await initTransporter();
  if (!transporter) {
    logger.info({ to }, "Password reset email skipped (no transport available)");
    return;
  }

  const resetUrl = `${env.APP_URL}/reset-password?token=${token}`;

  const html = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#12121a;border-radius:12px;border:1px solid #1e1e2e;padding:40px;">
    <h1 style="color:#00e5ff;font-size:24px;margin:0 0 8px;">Bannin</h1>
    <p style="color:#a0a0b0;font-size:14px;margin:0 0 24px;">&#30058;&#20154; -- Your AI Watchman</p>
    <p style="color:#e0e0e0;font-size:16px;line-height:1.6;margin:0 0 24px;">
      You requested a password reset. Click below to set a new password. This link expires in 1 hour.
    </p>
    <a href="${resetUrl}" style="display:inline-block;background:#00e5ff;color:#0a0a0f;font-weight:600;font-size:14px;padding:12px 28px;border-radius:8px;text-decoration:none;">
      Reset Password
    </a>
    <p style="color:#606070;font-size:12px;margin:24px 0 0;">
      If you didn't request a password reset, you can safely ignore this email.
    </p>
  </div>
</body>
</html>`;

  const text = `Bannin -- Password Reset\n\nReset your password: ${resetUrl}\n\nThis link expires in 1 hour. If you didn't request this, ignore this email.`;

  try {
    const info = await transporter.sendMail({
      from: env.SMTP_FROM,
      to,
      subject: "Reset your Bannin password",
      html,
      text,
    });
    logger.info({ to }, "Password reset email sent");

    const previewUrl = nodemailer.getTestMessageUrl(info);
    if (previewUrl) {
      logger.info({ previewUrl }, "View password reset email at this URL");
    }
  } catch (err) {
    logger.error({ err, to }, "Failed to send password reset email");
    throw new Error("Failed to send password reset email");
  }
}
