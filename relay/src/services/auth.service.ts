import { randomUUID } from "node:crypto";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { prisma } from "../lib/prisma.js";
import { getEnv } from "../config/env.js";
import { BCRYPT_ROUNDS, VERIFY_TOKEN_EXPIRY_HOURS, RESET_TOKEN_EXPIRY_HOURS } from "../constants.js";
import { AuthError, ConflictError, NotFoundError } from "../lib/errors.js";
import type {
  RegisterInput,
  LoginInput,
  UpdateProfileInput,
  ChangePasswordInput,
  DeleteAccountInput,
  ForgotPasswordInput,
  ResetPasswordInput,
} from "../schemas/auth.schema.js";
import type { JwtPayload } from "../types/index.js";

interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

interface UserResponse {
  id: string;
  username: string;
  displayName: string;
  email: string | null;
  emailVerified: boolean;
}

export async function register(input: RegisterInput): Promise<{ user: UserResponse; tokens: TokenPair; verifyToken: string | null }> {
  // Check username uniqueness
  const existingUsername = await prisma.user.findUnique({ where: { username: input.username } });
  if (existingUsername) {
    throw new ConflictError("Username already taken");
  }

  // Check email uniqueness if provided
  if (input.email) {
    const existingEmail = await prisma.user.findUnique({ where: { email: input.email } });
    if (existingEmail) {
      throw new ConflictError("Email already registered");
    }
  }

  const passwordHash = await bcrypt.hash(input.password, BCRYPT_ROUNDS);

  let verifyToken: string | null = null;
  let verifyTokenExp: Date | null = null;
  if (input.email) {
    verifyToken = randomUUID();
    verifyTokenExp = new Date(Date.now() + VERIFY_TOKEN_EXPIRY_HOURS * 60 * 60 * 1000);
  }

  const user = await prisma.user.create({
    data: {
      username: input.username,
      displayName: input.displayName,
      email: input.email ?? null,
      passwordHash,
      verifyToken,
      verifyTokenExp,
    },
  });

  const tokens = generateTokens({
    id: user.id,
    username: user.username,
    email: user.email,
    emailVerified: false,
  });

  return {
    user: {
      id: user.id,
      username: user.username,
      displayName: user.displayName,
      email: user.email,
      emailVerified: false,
    },
    tokens,
    verifyToken,
  };
}

export async function login(input: LoginInput): Promise<{ user: UserResponse; tokens: TokenPair }> {
  // Query by username OR email
  const user = await prisma.user.findFirst({
    where: {
      OR: [
        { username: input.identifier },
        { email: input.identifier },
      ],
    },
  });

  if (!user) {
    // Dummy bcrypt to prevent timing attacks on user enumeration
    await bcrypt.compare(input.password, "$2a$12$000000000000000000000000000000000000000000000000000000");
    throw new AuthError("Invalid credentials");
  }

  const valid = await bcrypt.compare(input.password, user.passwordHash);
  if (!valid) {
    throw new AuthError("Invalid credentials");
  }

  const tokens = generateTokens({
    id: user.id,
    username: user.username,
    email: user.email,
    emailVerified: user.emailVerified,
  });

  return {
    user: {
      id: user.id,
      username: user.username,
      displayName: user.displayName,
      email: user.email,
      emailVerified: user.emailVerified,
    },
    tokens,
  };
}

export async function verifyEmail(token: string): Promise<{ email: string }> {
  const user = await prisma.user.findUnique({ where: { verifyToken: token } });
  if (!user) {
    throw new NotFoundError("Invalid verification token");
  }
  if (user.verifyTokenExp && user.verifyTokenExp < new Date()) {
    throw new AuthError("Verification token has expired");
  }

  await prisma.user.update({
    where: { id: user.id },
    data: { emailVerified: true, verifyToken: null, verifyTokenExp: null },
  });

  return { email: user.email! };
}

export async function resendVerification(userId: string): Promise<{ verifyToken: string; email: string }> {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new NotFoundError("User not found");
  }
  if (!user.email) {
    throw new ConflictError("No email address on account");
  }
  if (user.emailVerified) {
    throw new ConflictError("Email already verified");
  }

  const verifyToken = randomUUID();
  const verifyTokenExp = new Date(Date.now() + VERIFY_TOKEN_EXPIRY_HOURS * 60 * 60 * 1000);

  await prisma.user.update({
    where: { id: userId },
    data: { verifyToken, verifyTokenExp },
  });

  return { verifyToken, email: user.email };
}

export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  const env = getEnv();
  let decoded: JwtPayload;
  try {
    decoded = jwt.verify(refreshToken, env.JWT_REFRESH_SECRET) as JwtPayload;
  } catch {
    throw new AuthError("Invalid refresh token");
  }

  const user = await prisma.user.findUnique({ where: { id: decoded.id } });
  if (!user) {
    throw new AuthError("User no longer exists");
  }

  return generateTokens({
    id: user.id,
    username: user.username,
    email: user.email,
    emailVerified: user.emailVerified,
  });
}

export async function getMe(userId: string): Promise<UserResponse & { createdAt: Date }> {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new NotFoundError("User not found");
  }
  return {
    id: user.id,
    username: user.username,
    displayName: user.displayName,
    email: user.email,
    emailVerified: user.emailVerified,
    createdAt: user.createdAt,
  };
}

export async function updateProfile(
  userId: string,
  input: UpdateProfileInput,
): Promise<{ user: UserResponse; verifyToken: string | null }> {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new NotFoundError("User not found");
  }

  const data: Record<string, unknown> = {};
  let verifyToken: string | null = null;

  if (input.displayName !== undefined) {
    data.displayName = input.displayName;
  }

  if (input.email !== undefined) {
    if (input.email === null) {
      // Removing email
      data.email = null;
      data.emailVerified = false;
      data.verifyToken = null;
      data.verifyTokenExp = null;
    } else if (input.email !== user.email) {
      // Changing email -- check uniqueness
      const existing = await prisma.user.findUnique({ where: { email: input.email } });
      if (existing && existing.id !== userId) {
        throw new ConflictError("Email already registered");
      }
      data.email = input.email;
      data.emailVerified = false;
      verifyToken = randomUUID();
      data.verifyToken = verifyToken;
      data.verifyTokenExp = new Date(Date.now() + VERIFY_TOKEN_EXPIRY_HOURS * 60 * 60 * 1000);
    }
  }

  if (Object.keys(data).length === 0) {
    return {
      user: {
        id: user.id,
        username: user.username,
        displayName: user.displayName,
        email: user.email,
        emailVerified: user.emailVerified,
      },
      verifyToken: null,
    };
  }

  const updated = await prisma.user.update({
    where: { id: userId },
    data,
  });

  return {
    user: {
      id: updated.id,
      username: updated.username,
      displayName: updated.displayName,
      email: updated.email,
      emailVerified: updated.emailVerified,
    },
    verifyToken,
  };
}

export async function changePassword(userId: string, input: ChangePasswordInput): Promise<void> {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new NotFoundError("User not found");
  }

  const valid = await bcrypt.compare(input.currentPassword, user.passwordHash);
  if (!valid) {
    throw new AuthError("Current password is incorrect");
  }

  const passwordHash = await bcrypt.hash(input.newPassword, BCRYPT_ROUNDS);
  await prisma.user.update({
    where: { id: userId },
    data: { passwordHash },
  });
}

export async function deleteAccount(userId: string, input: DeleteAccountInput): Promise<void> {
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) {
    throw new NotFoundError("User not found");
  }

  const valid = await bcrypt.compare(input.password, user.passwordHash);
  if (!valid) {
    throw new AuthError("Password is incorrect");
  }

  // Cascade delete (agents, snapshots, events, alerts, push subs)
  await prisma.user.delete({ where: { id: userId } });
}

export async function forgotPassword(input: ForgotPasswordInput): Promise<void> {
  // Find user by verified email only
  const user = await prisma.user.findUnique({ where: { email: input.email } });

  if (user && user.emailVerified) {
    const resetToken = randomUUID();
    const resetTokenExp = new Date(Date.now() + RESET_TOKEN_EXPIRY_HOURS * 60 * 60 * 1000);

    await prisma.user.update({
      where: { id: user.id },
      data: { resetToken, resetTokenExp },
    });

    // Return token for the controller to send email
    // We store it on the user and let the controller handle email sending
    return;
  }

  // Always return void (don't reveal if email exists)
}

export async function getForgotPasswordToken(email: string): Promise<string | null> {
  const user = await prisma.user.findUnique({
    where: { email },
    select: { resetToken: true, emailVerified: true },
  });
  if (user && user.emailVerified && user.resetToken) {
    return user.resetToken;
  }
  return null;
}

export async function resetPassword(input: ResetPasswordInput): Promise<void> {
  const user = await prisma.user.findUnique({ where: { resetToken: input.token } });
  if (!user) {
    throw new NotFoundError("Invalid reset token");
  }
  if (user.resetTokenExp && user.resetTokenExp < new Date()) {
    throw new AuthError("Reset token has expired");
  }

  const passwordHash = await bcrypt.hash(input.newPassword, BCRYPT_ROUNDS);
  await prisma.user.update({
    where: { id: user.id },
    data: { passwordHash, resetToken: null, resetTokenExp: null },
  });
}

function generateTokens(payload: JwtPayload): TokenPair {
  const env = getEnv();
  const accessToken = jwt.sign(payload, env.JWT_SECRET, { expiresIn: env.JWT_EXPIRES_IN } as jwt.SignOptions);
  const refreshToken = jwt.sign(payload, env.JWT_REFRESH_SECRET, { expiresIn: env.JWT_REFRESH_EXPIRES_IN } as jwt.SignOptions);
  return { accessToken, refreshToken };
}

export { AuthError, ConflictError, NotFoundError } from "../lib/errors.js";
