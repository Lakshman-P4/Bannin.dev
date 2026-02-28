import { getEnv } from "../config/env.js";
import { logger } from "../lib/logger.js";

const BREVO_API_URL = "https://api.brevo.com/v3/smtp/email";

interface BrevoEmailPayload {
  sender: { name: string; email: string };
  to: { email: string }[];
  subject: string;
  htmlContent: string;
  textContent: string;
}

async function sendEmail(payload: BrevoEmailPayload): Promise<void> {
  const env = getEnv();

  if (!env.BREVO_API_KEY || !env.EMAIL_FROM_ADDRESS) {
    logger.info("Email sending disabled (BREVO_API_KEY or EMAIL_FROM_ADDRESS not set)");
    return;
  }

  const res = await fetch(BREVO_API_URL, {
    method: "POST",
    headers: {
      "accept": "application/json",
      "api-key": env.BREVO_API_KEY,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Brevo API error ${res.status}: ${body}`);
  }

  logger.info({ to: payload.to[0]?.email }, "Email sent via Brevo API");
}

export async function sendVerificationEmail(to: string, token: string): Promise<void> {
  const env = getEnv();
  const verifyUrl = `${env.APP_URL}/verify?token=${token}`;

  const htmlContent = `
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

  const textContent = `Bannin -- Verify your email\n\nVerify your email: ${verifyUrl}\n\nIf you didn't request this, ignore this email.`;

  try {
    await sendEmail({
      sender: { name: env.EMAIL_FROM_NAME, email: env.EMAIL_FROM_ADDRESS },
      to: [{ email: to }],
      subject: "Verify your Bannin email",
      htmlContent,
      textContent,
    });
  } catch (err) {
    logger.error({ err, to }, "Failed to send verification email");
    throw new Error("Failed to send verification email");
  }
}

export async function sendPasswordResetEmail(to: string, token: string): Promise<void> {
  const env = getEnv();
  const resetUrl = `${env.APP_URL}/reset-password?token=${token}`;

  const htmlContent = `
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

  const textContent = `Bannin -- Password Reset\n\nReset your password: ${resetUrl}\n\nThis link expires in 1 hour. If you didn't request this, ignore this email.`;

  try {
    await sendEmail({
      sender: { name: env.EMAIL_FROM_NAME, email: env.EMAIL_FROM_ADDRESS },
      to: [{ email: to }],
      subject: "Reset your Bannin password",
      htmlContent,
      textContent,
    });
  } catch (err) {
    logger.error({ err, to }, "Failed to send password reset email");
    throw new Error("Failed to send password reset email");
  }
}
