import { Router } from "express";
import * as authController from "../controllers/auth.controller.js";
import { authMiddleware } from "../middleware/auth.js";
import { createAuthLimiter, createResendLimiter } from "../middleware/rateLimiter.js";
import { validate } from "../middleware/validate.js";
import {
  registerSchema,
  loginSchema,
  refreshSchema,
  updateProfileSchema,
  changePasswordSchema,
  deleteAccountSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
} from "../schemas/auth.schema.js";

export function createAuthRoutes(): Router {
  const router = Router();
  const authLimiter = createAuthLimiter();
  const resendLimiter = createResendLimiter();

  // Public
  router.post("/register", authLimiter, validate(registerSchema), authController.register);
  router.post("/login", authLimiter, validate(loginSchema), authController.login);
  router.get("/verify/:token", authController.verifyEmail);
  router.post("/refresh", validate(refreshSchema), authController.refresh);
  router.post("/forgot-password", authLimiter, validate(forgotPasswordSchema), authController.forgotPassword);
  router.post("/reset-password", validate(resetPasswordSchema), authController.resetPassword);

  // Authenticated
  router.get("/me", authMiddleware, authController.me);
  router.patch("/me", authMiddleware, validate(updateProfileSchema), authController.updateProfile);
  router.patch("/password", authMiddleware, validate(changePasswordSchema), authController.changePassword);
  router.delete("/me", authMiddleware, validate(deleteAccountSchema), authController.deleteAccount);
  router.post("/resend-verification", authMiddleware, resendLimiter, authController.resendVerification);

  return router;
}

// Default export for backward compatibility
export default createAuthRoutes();
