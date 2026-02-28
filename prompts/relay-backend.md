# Bannin Relay Server -- Backend Production Prompt

## Context

You are building the relay server for **Bannin** (番人, Japanese for "watchman") -- a free, open-source monitoring agent for AI developers, ML engineers, and anyone who runs long compute jobs and walks away.

Bannin already has a local Python agent (`pip install bannin && bannin start`) that monitors system resources, predicts OOM crashes, tracks training progress, scores LLM conversation health, fires smart alerts, and works in Google Colab and Kaggle notebooks. All with zero code changes and zero configuration.

**The problem**: You start a 6-hour training run. You close your laptop. You go to dinner. Three hours in, it OOM'd. You don't find out until you get back. Real examples from the community: OOM at epoch 51/60 after 8 hours (no notification), memory growing silently until crash at step 9,000 after hours of training, process "Killed" with no error message after 2.5 days.

**The solution**: This relay server bridges the gap between "works on localhost" and "works from anywhere." The local agent connects outbound via WebSocket, the relay stores events and forwards real-time data to the web dashboard, and you get push notifications when something needs attention. From your browser, your tablet, anywhere.

**The punchline**: "You hit run. You walk away. Then what?"

**Why this matters**: Across 23 sources (GitHub, mcpmarket.com, PulseMCP, npm, PyPI, VS Code Marketplace, Chrome Web Store, arXiv papers), 200+ monitoring tools were analyzed. Zero provide runtime OOM prediction + remote alerts + persistent history + LLM health scoring + training progress tracking + cloud notebook support in a single zero-config tool. W&B (10,800 stars) requires code instrumentation and costs money. Grafana requires hours of setup with Prometheus and PromQL. labml (2,100 stars) requires code changes and is training-focused only. nvtop/gpustat are local-only terminal tools. Bannin is the only zero-config intelligent monitoring agent for AI developers, and this relay server is what turns it from "another localhost tool" into a unique product category.

**Deployment target**: Railway (managed hosting). PostgreSQL and Redis provisioned by Railway.

## Technology Stack (Mandatory)

- **Runtime**: Node.js 20+ with TypeScript (strict mode)
- **Framework**: Express.js with typed middleware
- **WebSocket**: `ws` library with JSON message protocol
- **Database**: PostgreSQL 16 via Prisma ORM (`DATABASE_URL` env var)
- **Cache/PubSub**: Redis via `ioredis` (real-time state, WebSocket session management, rate limiting)
- **Authentication**: JWT (access + refresh tokens), `bcryptjs` for password and API key hashing, `jsonwebtoken` for signing
- **Email**: `nodemailer` with Gmail SMTP for transactional email (verification, recovery, notifications). Only used when user has provided an email address. Create a dedicated Gmail account (e.g. `bannin.watchman@gmail.com`), enable 2FA, generate an app password. Free: 500 emails/day. Upgrade to Resend with a custom domain later if needed.
- **Push Notifications**: `web-push` (VAPID-based browser push notifications)
- **Validation**: `zod` schemas for all inputs (HTTP requests and WebSocket messages)
- **Logging**: `pino` (structured JSON logging)
- **Security**: `helmet`, `compression`, `express-rate-limit`, `cors`
- **Testing**: `vitest`, `supertest`
- **Deployment**: Docker (multi-stage build) + Railway

## Authentication Model -- Email Optional

Bannin uses a **username-first** auth model. Email is optional and unlocks recovery + notification features when provided.

### Design Principles

1. **Zero-friction onboarding**: A user signs up with a username + password. That's it. They can start monitoring immediately. No email required, no verification gate, no "check your inbox" blocker.

2. **Email is a power-up, not a gate**: Users who add email gain: account recovery (forgot password), email notifications for critical alerts, and a verified identity badge. Users without email still get 100% of monitoring functionality.

3. **No feature gating behind email**: All core features (agents, dashboard, events, WebSocket, push notifications) work without email. The only things that require email are: password reset (needs somewhere to send the link) and email-based notifications (needs somewhere to send the email).

4. **Verification only when email exists**: If a user provides an email, we send a verification link. Unverified emails are not trusted for recovery or notifications. But unverified email never blocks access to any feature.

## Database Schema (Prisma)

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id              String    @id @default(uuid())
  username        String    @unique          // primary identifier, 3-30 chars, alphanumeric + underscore
  passwordHash    String
  displayName     String                     // shown in UI, can contain spaces/unicode
  email           String?   @unique          // optional -- unlocks recovery + email notifications
  emailVerified   Boolean   @default(false)  // only meaningful when email is set
  verifyToken     String?   @unique
  verifyTokenExp  DateTime?
  resetToken      String?   @unique          // password reset token (requires email)
  resetTokenExp   DateTime?
  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt
  agents          Agent[]
  pushSubs        PushSubscription[]

  @@index([username])
  @@index([email])
}

model Agent {
  id           String    @id @default(uuid())
  userId       String
  name         String
  apiKeyHash   String    @unique
  hostname     String?
  os           String?
  agentVersion String?
  lastSeen     DateTime?
  isOnline     Boolean   @default(false)
  createdAt    DateTime  @default(now())
  updatedAt    DateTime  @updatedAt
  user         User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  snapshots    MetricSnapshot[]
  events       Event[]
  alerts       AlertHistory[]

  @@index([userId])
}

model MetricSnapshot {
  id        String   @id @default(uuid())
  agentId   String
  timestamp DateTime @default(now())
  cpu       Float                    // cpu.percent from metrics payload (0-100)
  memory    Float                    // memory.percent from metrics payload (0-100)
  disk      Float                    // disk.percent from metrics payload (0-100)
  gpu       Float?                   // gpu[0].gpu_utilization_percent (null if no GPU)
  gpuMemory Float?                   // gpu[0].memory_percent (null if no GPU)
  network   Json?                    // full network object from metrics payload
  processes Json?                    // full process list (from most recent processes message)
  raw       Json?                    // complete original metrics payload for full fidelity
  agent     Agent    @relation(fields: [agentId], references: [id], onDelete: Cascade)

  @@index([agentId, timestamp])
}

model Event {
  id        String   @id @default(uuid())
  agentId   String
  type      String
  source    String   @default("agent")
  severity  String?
  message   String
  data      Json?
  timestamp DateTime @default(now())
  agent     Agent    @relation(fields: [agentId], references: [id], onDelete: Cascade)

  @@index([agentId, timestamp])
  @@index([agentId, type])
  @@index([type])
  @@index([severity])
  @@index([timestamp])
}

model AlertHistory {
  id           String    @id @default(uuid())
  agentId      String
  severity     String
  message      String
  value        Float?
  threshold    Float?
  acknowledged Boolean   @default(false)
  firedAt      DateTime  @default(now())
  resolvedAt   DateTime?
  agent        Agent     @relation(fields: [agentId], references: [id], onDelete: Cascade)

  @@index([agentId, firedAt])
  @@index([agentId, severity])
}

model PushSubscription {
  id        String   @id @default(uuid())
  userId    String
  endpoint  String   @unique
  keys      Json
  createdAt DateTime @default(now())
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
}
```

### tsvector Full-Text Search Migration

After `npx prisma db push`, run the following raw SQL migration to add full-text search on the Event table:

```sql
-- Add tsvector column
ALTER TABLE "Event" ADD COLUMN IF NOT EXISTS "search_vector" tsvector;

-- Populate existing rows
UPDATE "Event" SET "search_vector" = to_tsvector('english', coalesce("message", '') || ' ' || coalesce("type", '') || ' ' || coalesce("source", ''));

-- Create GIN index for fast search
CREATE INDEX IF NOT EXISTS "Event_search_vector_idx" ON "Event" USING GIN ("search_vector");

-- Auto-update trigger on insert/update
CREATE OR REPLACE FUNCTION event_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW."search_vector" := to_tsvector('english', coalesce(NEW."message", '') || ' ' || coalesce(NEW."type", '') || ' ' || coalesce(NEW."source", ''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS event_search_vector_trigger ON "Event";
CREATE TRIGGER event_search_vector_trigger
  BEFORE INSERT OR UPDATE ON "Event"
  FOR EACH ROW EXECUTE FUNCTION event_search_vector_update();
```

Place this in `prisma/migrations/add_tsvector.sql` and execute it in `src/lib/prisma.ts` on startup via `prisma.$executeRawUnsafe()`.

## API Endpoints

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | None | Create account with `username` + `password` + `displayName`. Optional `email`. Returns access + refresh tokens. If email provided, sends verification email. |
| POST | `/api/auth/login` | None | Username + password login (or email + password if user has email set). Returns tokens. Response includes `email` and `emailVerified` fields. |
| POST | `/api/auth/refresh` | None | Exchange refresh token for new access token. |
| GET | `/api/auth/me` | JWT | Return current user profile (username, displayName, email, emailVerified). |
| PATCH | `/api/auth/me` | JWT | Update displayName or add/change email. If email added or changed, triggers verification. |
| GET | `/api/auth/verify/:token` | None | Verify email address. Sets `emailVerified = true`. Returns success JSON. |
| POST | `/api/auth/resend-verification` | JWT | Resend verification email. Only works if user has an unverified email. Rate-limited: 1 per minute. |
| POST | `/api/auth/forgot-password` | None | Send password reset email. Requires email address. Returns 200 regardless (no email enumeration). |
| POST | `/api/auth/reset-password` | None | Reset password with token from email. Requires `token` + `newPassword`. |
| PATCH | `/api/auth/password` | JWT | Change password for logged-in user. Requires `{ currentPassword, newPassword }`. Bcrypt-verify current before setting new. |
| DELETE | `/api/auth/me` | JWT | Delete account permanently. Requires `{ password }` for confirmation. Cascading delete removes all agents, snapshots, events, alerts, push subscriptions. Returns 200 on success. |

### Registration Validation

```typescript
const registerSchema = z.object({
  username: z.string()
    .min(3).max(30)
    .regex(/^[a-zA-Z0-9_]+$/, 'Username: letters, numbers, underscores only')
    .transform(s => s.toLowerCase()),  // case-insensitive
  password: z.string().min(8).max(128),
  displayName: z.string().min(1).max(100).trim(),
  email: z.string().email().optional(),  // optional -- triggers verification if provided
});
```

### Login Validation

```typescript
const loginSchema = z.object({
  // Accept either username or email as the identifier
  identifier: z.string().min(1).max(320).transform(s => s.toLowerCase().trim()),
  password: z.string().min(1).max(128),
});
```

Login logic:
1. Lowercase and trim the `identifier`.
2. Query: `WHERE username = $1 OR email = $1` (single query, no sequential lookup).
3. If no user found, **always run a dummy `bcrypt.compare()` against a pre-generated hash** to normalize response time. This prevents timing side-channels that reveal whether a username or email exists.
4. Return "Invalid credentials" on all failure paths -- never "User not found" vs "Wrong password".

### Profile Update Validation

```typescript
const updateProfileSchema = z.object({
  displayName: z.string().min(1).max(100).trim().optional(),
  email: z.string().email().optional().nullable(),  // null to remove email
});
```

If email is added or changed: clear `emailVerified`, generate new `verifyToken`, send verification email. If email collides with another account, return 422 with `{ error: { code: "EMAIL_TAKEN", message: "Email already in use" } }`.

### Change Password Validation

```typescript
const changePasswordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: z.string().min(8).max(128),
});
```

### Delete Account Validation

```typescript
const deleteAccountSchema = z.object({
  password: z.string().min(1),  // confirm identity before irreversible action
});
```

### Agents (Protected -- JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List user's agents with online status. |
| POST | `/api/agents` | Register new agent. Returns agent object with raw API key (only time it's shown). |
| GET | `/api/agents/:id` | Agent detail including latest metrics snapshot. |
| PATCH | `/api/agents/:id` | Update agent name. |
| DELETE | `/api/agents/:id` | Remove agent and all its data (cascading delete). |
| POST | `/api/agents/:id/regenerate-key` | Generate new API key. Returns raw key (only time it's shown). Invalidates old key. |

**No email verification required for any agent endpoint.** Users can create agents and start monitoring immediately after registration.

### Dashboard Data (Protected -- JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard` | Overview: all agents with latest metrics, active alert counts. |
| GET | `/api/agents/:id/metrics` | Latest metric snapshot for agent. |
| GET | `/api/agents/:id/metrics/history` | Metric history. Query: `?minutes=30&limit=100&offset=0`. |
| GET | `/api/agents/:id/processes` | Latest process list from agent (from most recent snapshot). |
| GET | `/api/agents/:id/alerts` | Alert history for agent. Query: `?limit=50&offset=0&severity=critical`. |
| GET | `/api/agents/:id/events` | Event log for agent. Query: `?limit=50&offset=0&type=alert&severity=warning`. |

### Events (Protected -- JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/events` | All events across user's agents. Query: `?limit=50&offset=0&type=alert&severity=critical&agentId=uuid`. |
| GET | `/api/events/search` | Full-text search across events using PostgreSQL tsvector. Query: `?q=OOM&limit=50&offset=0`. |
| GET | `/api/events/timeline` | Events newest-first with agent labels. Query: `?limit=50&offset=0`. |

### Notifications (Protected -- JWT required)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/notifications/push/subscribe` | Register browser push subscription (PushSubscription JSON). |
| DELETE | `/api/notifications/push/unsubscribe` | Remove push subscription by endpoint. |
| POST | `/api/notifications/test` | Send a test push notification. |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | `{ status: "ok", timestamp, version, agents_connected }`. Railway health check. |

### Response Envelope

All endpoints use a consistent envelope:

**Success (single item)**:
```json
{ "data": { ... } }
```

**Success (paginated list)**:
```json
{ "data": [ ... ], "meta": { "total": 1234, "limit": 50, "offset": 0 } }
```

**Error**:
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Username is required" } }
```

HTTP status codes: 200 (ok), 201 (created), 400 (bad request), 401 (unauthorized), 404 (not found), 422 (validation error), 429 (rate limited), 500 (internal error).

**Note**: No 403 "email not verified" responses. Email verification never blocks access to any feature.

## Email Service -- Conditional Activation

The email service only sends emails when:
1. The user has an email address set
2. The action requires email (verification, password reset, alert notifications)

### Email Provider: Gmail SMTP (via Nodemailer)

No custom domain required. Use a dedicated Gmail account with an app password.

**Setup (one-time)**:
1. Create `bannin.watchman@gmail.com` (or similar)
2. Enable 2-Factor Authentication on the account
3. Go to Google Account -> Security -> App Passwords -> generate one for "Mail"
4. Use the 16-character app password as `SMTP_PASS`

```typescript
// src/services/email.service.ts
import nodemailer from 'nodemailer';
import { logger } from '../lib/logger';

const transporter = process.env.SMTP_USER
  ? nodemailer.createTransport({
      service: 'gmail',
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    })
  : null;

export async function sendVerificationEmail(to: string, token: string): Promise<void> {
  if (!transporter) {
    logger.warn('SMTP not configured -- skipping verification email');
    return;
  }
  await transporter.sendMail({
    from: `"Bannin" <${process.env.SMTP_USER}>`,
    to,
    subject: 'Verify your email -- Bannin',
    html: verificationTemplate(token),
    text: verificationPlainText(token),
  });
}
```

### Email Verification Flow

1. User registers or adds email via `PATCH /api/auth/me` -- `emailVerified` defaults to `false`. A random token (`crypto.randomUUID()`) is generated with 24-hour expiry.
2. Relay sends verification email via Gmail SMTP with a link: `{APP_URL}/verify?token={verifyToken}`. Email subject: "Verify your email -- Bannin". Human-friendly copy: "You added your email to Bannin. Click below to verify it so we can send you alerts and enable password recovery."
3. User clicks link -- frontend calls `GET /api/auth/verify/:token`. Relay validates token exists and is not expired, sets `emailVerified = true`, clears token fields.
4. Unverified emails are ignored for notifications and recovery. No access is blocked.
5. Verification emails use a clean HTML template matching Bannin's dark theme (dark background, cyan accent, Bannin eye logo). Plain-text fallback included.

### Password Reset Flow (Requires Verified Email)

1. User submits `POST /api/auth/forgot-password` with `{ email: "..." }`.
2. If email exists AND is verified, generate a reset token (UUID, 1-hour expiry), store in `resetToken`/`resetTokenExp`.
3. Send reset email: "Reset your Bannin password" with link `{APP_URL}/reset-password?token={resetToken}`.
4. `POST /api/auth/reset-password` with `{ token, newPassword }` -- validates token, hashes new password, clears token fields.
5. Always returns 200 on the forgot-password endpoint regardless of whether email exists (prevents email enumeration).

## WebSocket Protocol

### Agent -> Relay (`ws://relay/ws/agent?key=AGENT_API_KEY`)

The agent connects outbound. Auth via API key in query param (bcrypt-compared against stored hash). Messages are JSON with a `type` field.

**Security note**: Query params containing API keys and JWTs are visible in server logs and proxy logs. In production, ALL WebSocket connections MUST use WSS (TLS). The request logger (`pino-http`) MUST be configured to redact query params on WebSocket upgrade requests. Never log raw `key` or `token` query values.

All 8 message types match the Python agent's exact output shapes:

#### 1. `metrics` -- System metrics snapshot (every 10 seconds)

```typescript
{
  type: "metrics",
  timestamp: string,  // ISO8601
  data: {
    cpu: {
      percent: number,
      per_core: number[],
      count_physical: number,
      count_logical: number,
      frequency_mhz: number | null
    },
    memory: {
      total_gb: number,
      available_gb: number,
      used_gb: number,
      percent: number
    },
    disk: {
      total_gb: number,
      used_gb: number,
      free_gb: number,
      percent: number
    },
    network: {
      bytes_sent: number,
      bytes_received: number,
      bytes_sent_mb: number,
      bytes_received_mb: number
    },
    gpu: Array<{
      index: number,
      name: string,
      memory_total_mb: number,
      memory_used_mb: number,
      memory_free_mb: number,
      memory_percent: number,
      gpu_utilization_percent: number,
      temperature_c: number | null
    }> | null
  }
}
```

#### 2. `alert` -- Alert fired

```typescript
{
  type: "alert",
  timestamp: string,
  data: {
    id: string,
    severity: "info" | "warning" | "critical",
    message: string,
    value: number,
    threshold: number | null,
    fired_at: string,  // ISO8601
    fired_epoch: number
  }
}
```

#### 3. `oom_prediction` -- OOM prediction update

```typescript
{
  type: "oom_prediction",
  timestamp: string,
  data: {
    ram: {
      current_percent: number | null,
      trend: "increasing" | "decreasing" | "stable" | "no_data" | "insufficient_data",
      growth_rate_per_min?: number,
      confidence?: number,
      data_points?: number,
      minutes_until_full: number | null,
      estimated_full_at?: string | null,
      severity?: "critical" | "warning" | "info" | "ok" | "low_confidence"
    },
    gpu: Array<{
      index: number,
      name: string,
      current_percent: number,
      trend: string,
      growth_rate_per_min: number,
      confidence: number,
      data_points: number,
      minutes_until_full: number | null,
      severity: string
    }>,
    data_points: number,
    min_data_points_required: number
  }
}
```

#### 4. `training` -- Training progress update

```typescript
{
  type: "training",
  timestamp: string,
  data: {
    active_tasks: Array<{
      task_id: string,
      name: string,
      source: string,
      current: number,
      total: number | null,
      percent: number | null,
      elapsed_seconds: number,
      eta_seconds: number | null,
      eta_human: string | null,
      eta_timestamp: string | null,
      started_at: string,
      status: "running"
    }>,
    completed_tasks: Array<{ /* same shape, status: "completed" */ }>,
    stalled_tasks: Array<{ /* same shape, status: "stalled" */ }>,
    total_tracked: number
  }
}
```

#### 5. `event` -- Generic event from analytics pipeline

```typescript
{
  type: "event",
  timestamp: string,
  data: {
    ts: number,
    source: string,
    machine: string,
    type: string,
    severity: string | null,
    data: Record<string, unknown>,
    message: string
  }
}
```

#### 6. `processes` -- Process list update

```typescript
{
  type: "processes",
  timestamp: string,
  data: {
    summary: { total: number, running: number, sleeping: number },
    top_processes: Array<{
      name: string,
      category: string,
      cpu_percent: number,
      memory_percent: number,
      memory_mb: number,
      instance_count: number,
      pids: number[],
      description?: string
    }>,
    resource_breakdown: {
      cpu: Array<{ name: string, value: number, display: string }>,
      ram: Array<{ name: string, value: number, display: string }>
    }
  }
}
```

#### 7. `health` -- LLM/conversation health update

```typescript
{
  type: "health",
  timestamp: string,
  data: {
    health_score: number,
    rating: "excellent" | "good" | "fair" | "poor" | "critical",
    source?: string,
    components: Record<string, { score: number, weight: number, detail?: string }>,
    recommendation: string | null,
    per_source?: Array<{
      id: string,
      label: string,
      type: "mcp" | "ollama" | "api",
      health_score: number,
      rating: string,
      components: Record<string, unknown>,
      recommendation: string | null
    }>
  }
}
```

#### 8. `heartbeat` -- Keep-alive (every 30 seconds)

```typescript
{
  type: "heartbeat",
  timestamp: string,
  data: {
    uptime_seconds: number
  }
}
```

### Relay -> Dashboard Client (`ws://relay/ws/dashboard?token=JWT`)

Client connects with JWT in query param. After connection, client subscribes to specific agents:

```typescript
// Client sends:
{ type: "subscribe", agentId: string }
{ type: "unsubscribe", agentId: string }

// Relay forwards agent data wrapped with agentId:
{ type: "agent_metrics", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_alert", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_oom", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_training", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_event", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_processes", agentId: string, timestamp: string, data: { ... } }
{ type: "agent_health", agentId: string, timestamp: string, data: { ... } }

// Agent lifecycle:
{ type: "agent_status", agentId: string, status: "connected" | "disconnected" }
```

### Control Messages (Relay <-> Agent, Dashboard <-> Relay)

```typescript
// Dashboard -> Relay: request training stop
{ type: "training_stop", agentId: string, taskId: string }

// Relay -> Agent: forward stop request
{ type: "training_stop", taskId: string, signal: "SIGINT" }

// Relay -> Agent: force kill after grace period
{ type: "training_kill", taskId: string, signal: "SIGKILL" }

// Agent -> Relay -> Dashboard: stop confirmed
{ type: "training_stopped", taskId: string, status: "graceful" | "forced" }
```

These control messages MUST be included in `ws-messages.schema.ts` alongside the 8 data message types.

## Training Stop Protocol

When a dashboard client requests stopping a training task on a remote agent, the relay implements a two-step graceful shutdown:

1. **Dashboard sends**: `{ type: "training_stop", agentId: string, taskId: string }`
2. **Relay forwards to agent**: `{ type: "training_stop", taskId: string, signal: "SIGINT" }`
3. **Agent sends SIGINT** to the training process (allows checkpoint save)
4. **30-second grace period** -- relay starts a timer
5. **If agent confirms stop** within 30s: `{ type: "training_stopped", taskId: string, status: "graceful" }` -- relay forwards to dashboard
6. **If 30s expires without confirmation**: relay sends `{ type: "training_kill", taskId: string, signal: "SIGKILL" }` to agent
7. **Agent force-kills** the process and confirms: `{ type: "training_stopped", taskId: string, status: "forced" }`

The relay tracks pending stops in a Map with 30-second TTL timers.

## Event Search

Full-text search uses PostgreSQL's built-in tsvector. No external search engine required.

**Search API** (`GET /api/events/search?q=OOM&limit=50&offset=0`):

```sql
SELECT * FROM "Event"
WHERE "search_vector" @@ plainto_tsquery('english', $1)
  AND "agentId" IN (SELECT id FROM "Agent" WHERE "userId" = $2)
ORDER BY ts_rank("search_vector", plainto_tsquery('english', $1)) DESC, "timestamp" DESC
LIMIT $3 OFFSET $4;
```

**Persistence triggers**: Every `alert`, `oom_prediction` (severity critical/warning), and `training` (status completed/stalled) message from an agent is automatically persisted as an Event row. Metrics snapshots are persisted at a downsampled rate (one per 10 seconds, pruned after 24 hours).

## Push Notifications

When an agent sends a critical alert or OOM prediction with severity `critical` or `warning`, the relay:

1. Looks up the agent's owner (user)
2. Checks if the user has active push subscriptions
3. Sends browser push notification via `web-push` with VAPID keys

**Optionally, if the user has a verified email**, also sends an email notification for critical-severity alerts via Gmail SMTP.

**Human-friendly notification copy** (never robotic):

- OOM critical: "Your training might crash -- memory at {value}% and climbing"
- OOM warning: "Memory usage is growing -- {value}% used, might fill in ~{minutes}m"
- Alert critical: "GPU memory critical -- {value}% VRAM used"
- Training complete: "Training complete! Finished in {duration}."
- Training stalled: "Training might be stuck -- no progress for {minutes}m"
- Agent disconnected: "Lost connection to {agent_name}"

Notification payload shape:

```typescript
{
  title: "Bannin",
  body: string,  // human-friendly message above
  icon: "/bannin-eye.png",
  data: { agentId: string, type: string }
}
```

## Connection Management

- **Agent heartbeat timeout**: 60 seconds. If no heartbeat received, mark agent offline in database and notify subscribed dashboard clients.
- **Client ping/pong**: WebSocket-level ping every 30 seconds. Terminate unresponsive connections.
- **Agent reconnect**: Accept reconnection, update `lastSeen` and `isOnline`, notify dashboard clients of status change.
- **Redis pub/sub**: All WebSocket messages are published to Redis channels (`agent:{agentId}:data`). Dashboard handlers subscribe to these channels. This enables horizontal scaling -- multiple relay instances can serve different dashboard clients while receiving from any agent.
- **Connection registry**: In-memory Map tracks connected agents and dashboard clients per instance. Redis tracks global online status.

## Middleware & Error Handling

- **`authMiddleware`**: Extracts JWT from `Authorization: Bearer <token>`. Decodes and attaches `req.user = { id, username, email, emailVerified }`. Returns 401 on missing/invalid/expired token.
- **`errorHandler`**: Global error handler. Catches Zod errors (422), Prisma errors (400/404/409/500), JWT errors (401), and unknown errors (500). Always returns the standard error envelope.
- **`rateLimiter`**: 100 requests/min per IP globally. 5 requests/min on auth endpoints. 1 request/min on resend-verification.
- **`requestLogger`**: `pino-http` structured request logging.
- **`validate(schema)`**: Zod validation middleware factory. Validates `req.body`, `req.query`, or `req.params` against a Zod schema. Returns 422 on failure.

**No `requireVerified` middleware.** Email verification does not gate any endpoint. The email service internally checks `emailVerified` before sending notifications.

## Project Structure

```
bannin-relay/
  src/
    index.ts                    # Server bootstrap: Express + WebSocket + graceful shutdown
    app.ts                      # Express app factory: middleware, routes, error handler
    constants.ts                # Resource bounds, timeouts, version
    config/
      env.ts                    # Typed env loader with Zod validation and defaults
    lib/
      prisma.ts                 # Prisma client singleton + tsvector migration
      redis.ts                  # ioredis client singleton with reconnect
      logger.ts                 # pino logger instance
    middleware/
      auth.ts                   # JWT extraction + user attachment
      errorHandler.ts           # Global error handler
      rateLimiter.ts            # Rate limiting configs
      validate.ts               # Zod middleware factory
    routes/
      auth.routes.ts
      agents.routes.ts
      dashboard.routes.ts
      events.routes.ts
      notifications.routes.ts
      health.routes.ts
    controllers/
      auth.controller.ts
      agents.controller.ts
      dashboard.controller.ts
      events.controller.ts
      notifications.controller.ts
    services/
      auth.service.ts           # Registration, login, token management, password reset
      agents.service.ts         # Agent CRUD with API key hashing
      metrics.service.ts        # Metric snapshot persistence + pruning
      events.service.ts         # Event persistence + tsvector search
      alerts.service.ts         # Alert history persistence
      email.service.ts          # Gmail SMTP email (verification, reset, alert notifications)
      push.service.ts           # Web Push notification sender
    ws/
      agentHandler.ts           # Agent WebSocket connection handler
      dashboardHandler.ts       # Dashboard client WebSocket handler
      registry.ts               # In-memory connection registry (agents + clients)
      messages.ts               # Message type constants and forwarding logic
    schemas/
      auth.schema.ts            # Zod: register, login, refresh, forgot/reset password
      agents.schema.ts          # Zod: create agent, update agent
      events.schema.ts          # Zod: event query params, search params
      ws-messages.schema.ts     # Zod: all 8 agent message types + dashboard messages
    types/
      index.ts                  # Shared TypeScript interfaces (AgentMessage, DashboardMessage, etc.)
      express.d.ts              # Express Request augmentation (req.user)
  prisma/
    schema.prisma
    migrations/
      add_tsvector.sql          # tsvector column + trigger + GIN index
    seed.ts
  Dockerfile
  railway.toml
  docker-compose.yml            # Local dev: PostgreSQL 16 + Redis 7
  .env.example
  tsconfig.json
  package.json
  vitest.config.ts
  tests/
    setup.ts                    # Test setup (Prisma test client, cleanup)
    auth.test.ts
    agents.test.ts
    events.test.ts
    websocket.test.ts
    push.test.ts
  .gitignore
```

## Dockerfile (Production -- Multi-Stage)

```dockerfile
# Stage 1: Build
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY prisma ./prisma
RUN npx prisma generate
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Stage 2: Production
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN apt-get update -y && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/dist ./dist
COPY prisma ./prisma
EXPOSE 3001
USER node
CMD ["node", "dist/index.js"]
```

## railway.toml

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/api/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3

[service]
internalPort = 3001
```

## docker-compose.yml (Local Development)

PostgreSQL 16 + Redis 7 services. Relay service builds from Dockerfile, maps port 3001, depends on postgres and redis, mounts source for hot-reload with `tsx watch`.

```yaml
version: "3.8"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: bannin_relay
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

## Environment Variables (.env.example)

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bannin_relay
REDIS_URL=redis://localhost:6379
JWT_SECRET=change-me-in-production-use-64-char-random
JWT_REFRESH_SECRET=change-me-in-production-use-64-char-random
JWT_EXPIRES_IN=15m
JWT_REFRESH_EXPIRES_IN=7d
PORT=3001
ALLOWED_ORIGINS=http://localhost:3000
NODE_ENV=development
SMTP_USER=bannin.watchman@gmail.com
SMTP_PASS=your-gmail-app-password
APP_URL=http://localhost:3000
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_EMAIL=mailto:bannin.watchman@gmail.com
```

## Seed Data

`prisma/seed.ts` creates:

- Demo user (with email): `demo` / `demo1234` (email: `demo@example.com`, emailVerified: true, displayName: "Demo User")
- Demo user (without email): `guest` / `guest1234` (no email, displayName: "Guest User")
- Demo agent for each user: "Demo MacBook" and "Guest Workstation" with known API keys (hashed)
- 50 sample metric snapshots over the last hour (realistic CPU/RAM/disk values)
- 10 sample events: 4 alerts (2 critical, 2 warning), 3 training events (2 complete, 1 stalled), 2 OOM predictions, 1 generic event

## Scripts (package.json)

```json
{
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "db:push": "prisma db push",
    "db:migrate": "prisma migrate dev",
    "db:seed": "tsx prisma/seed.ts",
    "db:studio": "prisma studio",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc --noEmit"
  }
}
```

## Resource Bounds

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_SNAPSHOTS_PER_AGENT` | 8640 | 24 hours at 10s intervals. Pruned on write. |
| `MAX_EVENTS_PER_AGENT` | 100000 | ~30 days of events. Pruned on write. |
| `MAX_ALERTS_PER_AGENT` | 10000 | Alert history cap. Pruned on write. |
| `MAX_AGENTS_PER_USER` | 20 | Agent creation limit. |
| `MAX_PUSH_SUBS_PER_USER` | 10 | Push subscription limit. |
| `HEARTBEAT_TIMEOUT_MS` | 60000 | Agent offline after 60s silence. |
| `WS_PING_INTERVAL_MS` | 30000 | WebSocket ping frequency. |
| `TRAINING_STOP_GRACE_MS` | 30000 | Grace period before SIGKILL. |
| `SNAPSHOT_PRUNE_INTERVAL_MS` | 3600000 | Prune old snapshots every hour. |
| `MAX_WS_MESSAGE_SIZE` | 1048576 | 1 MB max WebSocket message. |
| `EVENTS_PAGE_LIMIT` | 100 | Max items per page for event queries. |
| `USERNAME_MIN_LENGTH` | 3 | Minimum username length. |
| `USERNAME_MAX_LENGTH` | 30 | Maximum username length. |
| `VERIFY_TOKEN_EXPIRY_HOURS` | 24 | Email verification token TTL. |
| `RESET_TOKEN_EXPIRY_HOURS` | 1 | Password reset token TTL. |

All constants live in `src/constants.ts`.

## Branding

**Visual identity**: The Bannin eye -- a stylized surveillance/watchman eye that opens when the system is active. This is the primary icon used in notifications, favicons, and the dashboard header.

**Text identity**: 番人 (Bannin) -- the Japanese kanji appears alongside the eye as a secondary mark. The kanji reinforces the "watchman" meaning.

**Notification icon**: `/bannin-eye.png` -- the eye icon, used in push notification payloads and email headers.

**Email template header**: Include the Bannin eye logo + "番人 Bannin" text in all transactional emails. Dark background (#040506), cyan accent (#00d4ff).

## Build Verification

After generating all code:

1. `npm install` -- zero errors
2. `npx tsc --noEmit` -- zero type errors
3. `npx prisma validate` -- schema valid
4. `npx vitest run` -- all tests pass
5. `docker build -t bannin-relay .` -- builds clean
6. Initialize git repository, create `.gitignore`, commit: `feat: Bannin Relay Server -- WebSocket relay for remote monitoring`

## Principal Engineer Review Protocol

After the build passes, conduct a full code review as if you are a principal/staff engineer at Google, Stripe, or Cloudflare reviewing a production service that will run 24/7 handling real user data. This is not a formality -- this is the quality gate. Ship nothing that would not survive this review at those companies.

### Review Process

1. Review every file, top to bottom. No skimming. No "this looks fine."
2. For each issue found, classify severity:
   - **Critical (C)**: Security vulnerability, data loss risk, crash under normal operation, auth bypass
   - **High (H)**: Race condition, resource leak, unbounded collection, missing error handling on a likely failure path
   - **Medium (M)**: Type safety gap, missing validation, inconsistent error response, logging sensitive data
   - **Low (L)**: Naming inconsistency, dead code, missing JSDoc on a public API, suboptimal but correct logic
3. Fix each issue individually. Do not batch fixes. Verify the fix compiles and tests pass after each.
4. After all issues are fixed, re-review from scratch. New eyes, full pass.
5. Repeat until a full review pass finds **zero issues at any severity level**. Only then is the review PASS.

### Review Checklist (Every File, Every Time)

**Security (the non-negotiable layer)**:
- [ ] JWT validation: reject expired, malformed, wrong-algorithm tokens. Do not accept `alg: none`.
- [ ] API key comparison: constant-time bcrypt comparison only. Never string equality.
- [ ] No API keys, passwords, tokens, or JWTs in log output. Grep all `logger.*` calls.
- [ ] No username/email enumeration: login error says "Invalid credentials" not "User not found" vs "Wrong password". Forgot-password always returns 200.
- [ ] SQL injection: all queries use Prisma parameterized queries or `$queryRaw` with tagged templates. No string concatenation into SQL.
- [ ] WebSocket auth: API key validated before any message processing. Invalid key = immediate close.
- [ ] CORS: `ALLOWED_ORIGINS` env var parsed and applied. Never `*` outside development.
- [ ] Rate limiting: auth endpoints (5/min), verification resend (1/min), global (100/min). Verify limits are enforced.
- [ ] Helmet security headers applied.
- [ ] No `eval()`, `Function()`, or dynamic `require()` with user input.
- [ ] Password hashing: bcrypt with cost factor >= 10. Never SHA-256, MD5, or plain text.
- [ ] Token entropy: `crypto.randomUUID()` for verification/reset tokens. Never `Math.random()`.

**Type Safety**:
- [ ] Every function has explicit parameter types and return type.
- [ ] No `any` type except in genuinely polymorphic utility code. Every `as` cast has a comment explaining why it is safe.
- [ ] Zod schemas validate all request bodies, query params, and WebSocket messages. No raw `req.body` access without validation.
- [ ] Prisma types used for database operations. No manual `as` casting of query results.
- [ ] Express `req.user` type augmentation matches the actual JWT payload shape.

**Error Handling**:
- [ ] Every async function has error handling (try/catch, `.catch()`, or propagation to error middleware).
- [ ] Global error handler catches Zod (422), Prisma (mapped to 400/404/409/500), JWT (401), and unknown (500). Always returns the standard error envelope.
- [ ] No `catch {}` or `catch (e) {}` -- every catch either logs with context or returns a structured error.
- [ ] Database connection failures handled gracefully (log + 503, not unhandled promise rejection).
- [ ] Redis connection failures do not crash the server. Graceful degradation: in-memory fallback or skip non-critical operations.
- [ ] WebSocket errors do not crash the process. Each connection handler is isolated.

**Concurrency & Resource Management**:
- [ ] No unbounded collections. Every Map, Set, Array used as a cache or buffer has a maximum size or TTL.
- [ ] WebSocket connection registry cleans up on disconnect. No leaked entries.
- [ ] Heartbeat timers are cleared on connection close. No orphaned `setInterval`/`setTimeout`.
- [ ] Training stop grace period timers are cleared on confirmation or disconnect.
- [ ] Prisma client is a singleton. No connection pool exhaustion from multiple instances.
- [ ] Redis subscriptions are cleaned up on client disconnect.
- [ ] Database pruning runs on a bounded interval with row limits per operation (no `DELETE FROM ... WHERE` without `LIMIT`).

**Data Integrity**:
- [ ] Cascading deletes: deleting a user removes agents, snapshots, events, alerts, push subscriptions.
- [ ] Unique constraints enforced at database level (username, email, apiKeyHash, push endpoint).
- [ ] Timestamps use UTC consistently. No mixing of local time and UTC.
- [ ] Pagination: `limit` clamped to `EVENTS_PAGE_LIMIT`. `offset` validated as non-negative integer.
- [ ] API key generation: sufficient entropy (>= 32 bytes, base64-encoded). Hash before storage.

**Operational Readiness**:
- [ ] Health endpoint returns actual liveness data (DB connected, Redis connected, agent count).
- [ ] Structured logging (pino JSON) with request IDs for traceability.
- [ ] Graceful shutdown: close WebSocket connections, flush pending writes, disconnect Prisma/Redis, then exit.
- [ ] Startup banner logs port, environment, database connection status, and route count.
- [ ] No hardcoded secrets, ports, or URLs. Everything from environment variables with validated defaults.
- [ ] Dockerfile: non-root user (`USER node`), minimal image (no dev dependencies in production stage).

**Testing**:
- [ ] Auth tests: register (with email, without email), login (by username, by email), refresh, forgot-password, reset-password, verify email.
- [ ] Agent tests: CRUD, API key generation/regeneration, key hashing, ownership enforcement.
- [ ] WebSocket tests: agent auth, message forwarding, heartbeat timeout, dashboard subscription, reconnect.
- [ ] Event tests: persistence, search (tsvector), pagination, filtering by type/severity.
- [ ] Push notification tests: subscription CRUD, notification delivery on critical alert.
- [ ] Error case tests: invalid input (422), missing auth (401), wrong owner (404), rate limiting (429).

### Review Report Format

After each review pass, output:

```
## Review Pass N

| # | Severity | File | Line | Issue | Fix |
|---|----------|------|------|-------|-----|
| 1 | C | auth.service.ts | 42 | Password compared with === instead of bcrypt | Use bcrypt.compare() |
| 2 | H | registry.ts | 88 | Agent map never cleaned on disconnect | Add cleanup in close handler |

**Result**: FAIL (2C, 1H, 3M) -- fix all and re-review
```

Continue until:

```
## Review Pass N

No issues found.

**Result**: PASS
```

## IMPORTANT CONSTRAINTS

1. **No AI/LLM calls in the relay.** Intelligence lives in the Python agent. The relay is a dumb pipe + persistence layer.
2. **No external file storage.** Everything in PostgreSQL or Redis.
3. **Stateless design.** JWT-only auth. Ready for horizontal scaling with Redis pub/sub.
4. **Agent NEVER exposes ports** -- it connects outbound to the relay. Security by design.
5. **API keys are bcrypt-hashed.** Raw key shown only on create and regenerate. Never stored in plaintext. Never logged.
6. **Human-friendly notification copy.** Not "ALERT: RAM_HIGH", but "Your training might crash -- memory at 92%."
7. **Consistent response envelope.** `{ data: T }` for success, `{ data: T[], meta: { total, limit, offset } }` for paginated lists, `{ error: { code, message } }` for failures.
8. **No ELK/Elasticsearch.** PostgreSQL tsvector handles all search needs.
9. **Bound everything.** Every collection, query result, and WebSocket buffer has a maximum size defined in constants.ts.
10. **No silent failures.** Every error is logged with context or returned to the caller.
11. **Email is never a gate.** No feature requires email. No middleware blocks access based on email verification status. Email is a power-up for recovery and notifications.
12. **No email enumeration.** Login accepts "identifier" (username or email). Forgot-password always returns 200. Register checks username uniqueness (not email) as the primary conflict surface.
