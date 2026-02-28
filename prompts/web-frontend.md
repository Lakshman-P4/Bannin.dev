# Bannin Web Dashboard -- Frontend Production Prompt

## Context

You are building the web dashboard for **Bannin** (番人, Japanese for "watchman") -- the remote monitoring interface for a free, open-source monitoring agent used by AI developers, ML engineers, and anyone who runs long compute jobs.

The local Bannin agent runs on the user's machine, collects system metrics, predicts OOM crashes, tracks training progress, and fires smart alerts. The relay server (separate backend) receives this data via WebSocket. This dashboard connects to the relay to show real-time metrics from anywhere -- your browser, your tablet, your second machine.

**The punchline**: "You hit run. You walk away. Then what?"

**Who uses this**: AI-augmented engineers, ML engineers, data scientists running training jobs, developers using Claude Code / Cursor / Windsurf, students running experiments on Google Colab / Kaggle. Anyone who starts something and walks away.

**Why it matters**: Across 23 research sources and 200+ monitoring tools analyzed (GitHub, mcpmarket.com, PulseMCP, npm, PyPI, VS Code Marketplace, Chrome Web Store, arXiv papers, industry surveys), not a single free tool combines zero-config setup + runtime OOM prediction + remote access + LLM health monitoring + training progress tracking + cloud notebook support. This dashboard is what turns Bannin from "another localhost monitoring tool" into the only tool that lets AI developers check on their compute from anywhere with intelligence that predicts problems before they happen. 24% of all DL jobs fail. OOM causes ~9% of training failures. 60-70% of GPU budgets are wasted on idle resources. These are real problems with no adequate free solution -- until now.

This frontend consumes the Bannin Relay Server API (documented below) and is deployed on Vercel.

## Technology Stack (Mandatory)

- **Framework**: Next.js 14+ with App Router (TypeScript, strict mode)
- **Styling**: Tailwind CSS v3 with custom design tokens matching Bannin's signature dark theme
- **Animations**: Framer Motion for page transitions, staggered reveals, micro-interactions
- **Icons**: Lucide React
- **Forms**: React Hook Form + Zod validation (mirror backend schemas)
- **HTTP Client**: Native `fetch` with a typed API client wrapper (no Axios)
- **Real-time**: Native WebSocket client with auto-reconnect
- **State**: React Context for auth, Zustand for dashboard state
- **Fonts**: Self-hosted via `next/font` -- Space Grotesk (display/headings, via `next/font/google`) + DM Sans (body, via `next/font/google`) + JetBrains Mono (data/metrics, via `next/font/google`). NO Inter, Roboto, or system fonts. (Note: DM Sans substitutes for General Sans which is not on Google Fonts.)
- **Toast**: Sonner
- **Deployment**: Vercel

## Design Direction -- "Bannin Dark"

The design extends Bannin's existing signature aesthetic: a near-black palette with glassmorphism, cyan accents, and urgency-driven color states. This is a monitoring tool -- information density matters, but so does visual clarity. The design should feel like a premium developer tool (Linear, Vercel, Raycast caliber), not a generic dashboard template.

### Color System

```
// Backgrounds (layered darks, not pure black)
--bg-body:       #040506
--bg-card:       #0a0c10
--bg-card-glass: rgba(10, 12, 16, 0.85)  // with backdrop-blur
--bg-raised:     #12121a

// Borders
--border:        #141c28
--border-glow:   rgba(0, 212, 255, 0.08)

// Accent (Bannin's signature cyan)
--cyan:          #00d4ff
--cyan-glow:     0 0 18px rgba(0, 212, 255, 0.35)

// Status colors
--green:         #00ff88    // healthy, connected, complete
--amber:         #f0a500    // warning, 60-80% usage
--red:           #ff4444    // critical, 80%+ usage, errors

// Text
--text-primary:  #e4ecf7
--text-secondary:#5a7090
--text-muted:    #2e3d50
```

### Urgency States

Metric cards change appearance based on value:
- **Normal (0-60%)**: Cyan accent, default card style
- **Warning (60-80%)**: Amber border glow, amber text for value
- **Critical (80%+)**: Red pulsing border animation, red text, subtle red glow

### Typography

- **Display (headings)**: Space Grotesk -- geometric, technical, beautiful
- **Body**: DM Sans -- clean, readable, professional (substitutes for General Sans)
- **Data/Metrics**: JetBrains Mono -- monospace for numbers, percentages, timestamps

### Glassmorphism Cards

```css
background: rgba(10, 12, 16, 0.85);
backdrop-filter: blur(8px);
border: 1px solid rgba(20, 28, 40, 0.8);
border-radius: 14px;
```

On hover: subtle cyan border glow + slight lift.

## Branding -- The Bannin Eye

The primary visual identity is the **Bannin eye** -- a stylized surveillance/watchman eye. It is the logo, the favicon, the loading indicator, and the avatar.

### Eye Behavior
- **Loading state**: The eye is closed (a horizontal line). It blinks open when data arrives.
- **Active/healthy state**: The eye is open, pupil glows cyan.
- **Warning state**: The eye pupil shifts to amber.
- **Critical state**: The eye pulses red, pupil dilated.
- **Offline/disconnected**: The eye closes, dims to muted gray.

### Logo Composition
- Primary: Bannin eye icon (SVG, scalable)
- Secondary: "番人" kanji beside or below the eye
- Text: "Bannin" in Space Grotesk next to the icon
- Use the eye alone for favicon, notification icon, and compact spaces
- Use eye + "Bannin" for the navbar and landing page
- Use eye + "番人 Bannin" for the landing hero and footer

### Where the Eye Appears
- **Navbar**: Left-aligned, eye icon + "Bannin" text. Clicking the logo/text links back to `/` (landing page for unauthenticated users, `/dashboard` for authenticated users)
- **Favicon**: Eye icon only (`/bannin-eye.svg`)
- **Landing hero**: Large eye with subtle glow animation, kanji below
- **Dashboard header**: Small eye with status-reactive color (green/amber/red based on worst agent state)
- **Loading states**: Eye blink animation (closed -> open) replaces generic spinners
- **Notification icon**: Eye icon in push notifications (`/bannin-eye.png`)
- **Empty states**: Closed eye with "Bannin is watching... waiting for data" message

## Page Structure & Routes

### Public Routes (No auth)

| Route | Page | Description |
|-------|------|-------------|
| `/` | Landing Page | Hero, problem/solution, features, setup guide. Must make the use case immediately clear. |
| `/login` | Login | Username + password (or email + password). Link to register. |
| `/register` | Register | Username + display name + password. Optional email field. Auto-login after. |
| `/verify` | Email Verification | Reads `?token=` from URL, calls `GET /api/auth/verify/:token`. Shows success/error state. Only visited from email links. |
| `/reset-password` | Password Reset | Reads `?token=` from URL. New password form. Only visited from email links. |
| `/forgot-password` | Forgot Password | Enter email to receive reset link. Only useful for users who added email. |

### Protected Routes (Redirect to /login if no token)

| Route | Page | Description |
|-------|------|-------------|
| `/setup` | Setup Wizard | Post-registration: install agent, get API key, connect, confirm data flowing. Shown if user has no agents. No email verification required. |
| `/dashboard` | Dashboard | Real-time overview of connected agent: metrics, alerts, training status, OOM prediction. |
| `/events` | Events / Logs | Full event history with search, filtering by type/severity, timeline view. |
| `/settings` | Settings | Notification preferences, agent management, account settings, add/manage email. |

### Authentication Model -- Email Optional

The frontend mirrors the backend's username-first auth model:

1. **Registration requires**: username + display name + password. Email is an optional field with a clear label: "Add email for account recovery and alert notifications (optional)."

2. **No email verification blocker**: After registration, user goes straight to `/setup` or `/dashboard`. No "check your inbox" interstitial. No verification banner blocking access.

3. **Verification banner (conditional)**: If a user has provided an email but it is unverified, show a subtle (non-blocking) info banner on the dashboard: "Verify your email to enable password recovery and email alerts. Check your inbox or [resend]." This banner is dismissible and never blocks any functionality.

4. **Add email later**: The `/settings` page has an "Email" section where users can add, change, or remove their email. Adding email triggers a verification flow.

5. **Forgot password**: The `/forgot-password` page explains: "Enter the email address linked to your account. If you didn't add an email, you'll need to create a new account." This is honest and frictionless.

6. **Login flexibility**: Login form accepts either username or email in a single "Username or email" field.

## Landing Page -- Design Specification

This is the first thing people see. It must communicate the problem and solution in under 5 seconds.

### Hero Section

- Full viewport height, dark gradient mesh background
- **Bannin eye logo** centered above the headline, large (120-160px), with a subtle cyan glow pulse animation. The eye opens on page load with a smooth animation (0.8s ease-out).
- Animated headline: **"You hit run. You walk away. Then what?"** -- words animate in sequentially
- Below the headline, smaller: **"番人"** in a muted secondary style
- Subtitle: "Bannin watches your machine, your training runs, and your AI tools. Get alerts before things crash. Check in from anywhere. Zero setup."
- Two CTAs: "Get Started Free" (cyan, prominent) and "See How It Works" (ghost/outline)
- Background: subtle animated gradient mesh (CSS radial gradients with slow animation)

### Problem / Solution Section

Split layout:
- Left: **"The Problem"** -- "Your training OOMs at hour 3. Your Colab session disconnects. Your GPU runs out of VRAM. You don't find out until you get back."
- Right: **"The Solution"** -- "Bannin runs in the background. It predicts crashes before they happen. It sends you a notification. You check in from any browser."

### Features Section (3 cards)

1. **"Predict, Don't React"** -- OOM prediction with confidence scores. Know 12 minutes before your training crashes.
2. **"Check In From Anywhere"** -- Real-time dashboard in your browser. Metrics, alerts, training progress.
3. **"Two Minutes to Set Up"** -- `pip install bannin && bannin start`. Connect to the web. Done.

Cards animate in on scroll with Framer Motion `whileInView`.

### Setup Preview

Show the 3-step setup visually:
```
Step 1: pip install bannin
Step 2: bannin start
Step 3: Connect on bannin.vercel.app
```

### Footer

Minimal. Bannin eye icon + "番人 Bannin -- watchman for your compute." GitHub link.

## Setup Wizard (/setup)

Shown after first registration when user has no agents. **No email verification required.** Feels welcoming, not intimidating.

### Step 1: Install the Agent
"First, install Bannin on the machine you want to monitor."
Code block: `pip install bannin`
Platform-specific notes (Windows: `python -m bannin.cli start`, macOS: `python3`).

### Step 2: Get Your API Key
Auto-generates an agent when user clicks "Create Agent."
Shows the API key prominently with copy button.
"Save this key -- you'll need it to connect."

### Step 3: Connect
"Start the agent with your relay key:"
Code block: `bannin start --relay YOUR_API_KEY`
(Or show how to set BANNIN_RELAY_KEY env var)

### Step 4: Confirm
Live check: WebSocket listens for the agent to connect.
Shows a pulsing Bannin eye (closed, blinking) as "Waiting for connection..." state.
When agent connects: eye opens fully with cyan glow + "Connected! Metrics are flowing."
CTA: "Go to Dashboard"

## Dashboard (/dashboard) -- Core Experience

The dashboard shows real-time data from the connected agent via WebSocket. It should feel alive -- metrics update in real-time, not on refresh.

### Layout

Top: Agent name + status badge (green "Online" / red "Offline") + last seen timestamp. Small Bannin eye icon that reflects agent status (green pupil = online, gray = offline).

Main grid (responsive, 2-column on desktop):
- **Metric Cards** (top row): CPU, RAM, Disk, GPU -- each with percentage, visual bar, urgency state
- **OOM Prediction** card: confidence score, time-to-crash estimate, severity badge. "Memory will be full in ~12 minutes" or "Looking good -- no memory pressure detected"
- **Active Alerts** card: list of current alerts with severity badges and timestamps
- **Training Progress** card: if training detected, show task name, progress bar, ETA. If none: "No training runs detected."
- **Memory Trend Chart**: 5-minute rolling chart (Recharts) showing memory percentage over time. Cyan line, dark fill.
- **Recent Events** feed: last 10 events in reverse chronological. Each event has icon, message, timestamp. Click to expand.

### Real-time Updates

- Connect via WebSocket to relay: `ws://relay/ws/dashboard?token=JWT`
- Send `{ type: "subscribe", agentId: "..." }` on connect
- Update metric cards, alerts, training status, and event feed as messages arrive
- Auto-reconnect on disconnect with exponential backoff (1s, 2s, 4s, max 30s)
- Show connection status indicator using the Bannin eye (cyan = connected, amber = reconnecting, gray/closed = disconnected)

### Empty States

- No agent connected: Bannin eye closed + "No agent connected. Let's fix that -- it takes 2 minutes." + link to setup wizard
- Agent offline: Bannin eye dimmed + "Your agent is offline. Last seen: 2 hours ago. Start it with: `bannin start --relay YOUR_KEY`"
- No alerts: "All clear -- no alerts right now." (with small green checkmark)
- No training: "No training runs detected. Bannin watches for tqdm progress bars and training patterns automatically."

### Human Tone

Every piece of text should feel like a knowledgeable friend:
- "Memory is climbing -- 78% and trending up. Keep an eye on this."
- "Your training is 64% done. ETA: about 45 minutes."
- "Heads up -- OOM likely in ~8 minutes. Consider freeing some memory."

## Events Page (/events)

Full event log with:
- Search bar (full-text search across event messages)
- Filter chips: All, Alerts, Training, OOM, System
- Severity filter: All, Critical, Warning, Info
- Time range: Last hour, Last 24h, Last 7 days, Custom
- Event list: Each event shows severity badge, type icon, message, timestamp, agent name
- Pagination (load more on scroll or explicit "Load more" button)

## Settings Page (/settings)

### Email Management
- **If no email**: Show "Add email" form with explanation: "Add your email to enable password recovery and email notifications for critical alerts."
- **If email unverified**: Show email with "Unverified" badge + "Resend verification" button + option to change email
- **If email verified**: Show email with "Verified" checkmark + option to change email
- Changing email clears verification and triggers new verification

### Notifications
- Toggle: "Enable browser push notifications" (triggers Web Push permission prompt + registers service worker `sw.js`)
- Test notification button
- Notification preferences: which alert severities trigger push (critical only, critical + warning, all)
- If email verified: additional toggle for "Email me on critical alerts"
- Service worker (`public/sw.js`) handles `push` event (show notification) and `notificationclick` event (open dashboard for the relevant agent). Register the SW in `AuthProvider` or root `layout.tsx` on first load.

### Agent Management
- List of user's agents with name, status, last seen
- Edit agent name
- Regenerate API key (with confirmation)
- Delete agent (with confirmation)

### Account
- Update display name
- Change password
- Delete account (with confirmation)

## API Client

Create a typed API client at `lib/api.ts`:

```typescript
const api = {
  auth: {
    register(data: RegisterInput): Promise<AuthResponse>,
    login(data: LoginInput): Promise<AuthResponse>,
    refresh(): Promise<AuthResponse>,
    me(): Promise<User>,
    updateProfile(data: UpdateProfileInput): Promise<User>,
    verifyEmail(token: string): Promise<void>,
    resendVerification(): Promise<void>,
    forgotPassword(email: string): Promise<void>,
    resetPassword(token: string, password: string): Promise<void>,
    changePassword(data: ChangePasswordInput): Promise<void>,
    deleteAccount(password: string): Promise<void>,
  },
  agents: {
    list(): Promise<Agent[]>,
    create(data: CreateAgentInput): Promise<Agent>,
    get(id: string): Promise<Agent>,
    update(id: string, data: UpdateAgentInput): Promise<Agent>,
    delete(id: string): Promise<void>,
    regenerateKey(id: string): Promise<{ apiKey: string }>,
    metrics(id: string): Promise<MetricSnapshot>,
    metricsHistory(id: string, minutes?: number): Promise<MetricSnapshot[]>,
    processes(id: string): Promise<ProcessList>,
    alerts(id: string, page?: number): Promise<PaginatedAlerts>,
    events(id: string, params?: EventFilters): Promise<PaginatedEvents>,
  },
  events: {
    list(params?: EventFilters): Promise<PaginatedEvents>,
    search(query: string): Promise<PaginatedEvents>,
    timeline(params?: TimelineFilters): Promise<PaginatedEvents>,
  },
  notifications: {
    subscribePush(subscription: PushSubscriptionJSON): Promise<void>,
    unsubscribePush(endpoint: string): Promise<void>,
    test(): Promise<void>,
  },
  dashboard: {
    overview(): Promise<DashboardOverview>,
  },
}
```

- Base URL from `NEXT_PUBLIC_API_URL` environment variable
- Auto-attach JWT from localStorage
- Handle 401 by clearing auth and redirecting to /login
- Handle token refresh transparently
- All methods return typed responses

## Auth Implementation

- Store tokens in localStorage with in-memory cache
- AuthProvider wrapping the app in root layout
- `useAuth()` hook: `{ user, isLoading, isAuthenticated, hasEmail, isEmailVerified, login, register, logout, updateProfile, resendVerification }`
- Protected route layout that redirects to `/login` with return URL
- On app load, call `/api/auth/me` to validate token

## WebSocket Hook

`useAgentSocket(agentId: string)` custom hook:
- Connects to relay WebSocket with JWT: `wss://{RELAY}/ws/dashboard?token={JWT}`
- Sends `{ type: "subscribe", agentId }` on connect
- Handles incoming messages prefixed with `agent_` (relay wraps all forwarded data):
  - `agent_metrics` -> updates `metrics` state
  - `agent_alert` -> appends to `alerts` list
  - `agent_oom` -> updates `oomPrediction` state
  - `agent_training` -> updates `training` state
  - `agent_event` -> appends to `events` feed
  - `agent_processes` -> updates `processes` state
  - `agent_health` -> updates `health` state (LLM conversation health)
  - `agent_status` -> updates `isOnline` (connected/disconnected)
- Returns: `{ metrics, alerts, oomPrediction, training, events, processes, health, isOnline, isConnected }`
- Auto-reconnects with exponential backoff (1s, 2s, 4s... max 30s)
- Cleans up on unmount (unsubscribe + close)

## Project Structure

```
bannin-web/
  src/
    app/
      layout.tsx                # Root layout: providers, fonts, global styles
      page.tsx                  # Landing page
      login/page.tsx
      register/page.tsx
      verify/page.tsx           # Email verification (from email link)
      forgot-password/page.tsx  # Request password reset
      reset-password/page.tsx   # Set new password (from email link)
      (protected)/
        layout.tsx              # Auth guard wrapper
        setup/page.tsx          # Setup wizard
        dashboard/page.tsx      # Real-time dashboard
        events/page.tsx         # Event log
        settings/page.tsx       # Settings
      not-found.tsx             # Custom 404 page with navigation to dashboard
      globals.css
    components/
      ui/                       # Button, Input, Card, Badge, Modal, Toast, etc.
      landing/                  # Hero, Features, SetupPreview, Footer
      setup/                    # SetupWizard steps
      dashboard/                # MetricCard, AlertList, TrainingProgress, MemoryChart, EventFeed, OOMCard
      events/                   # EventList, EventFilters, SearchBar
      settings/                 # NotificationSettings, AgentList, AccountSettings, EmailSettings
      auth/
        AuthProvider.tsx
        LoginForm.tsx
        RegisterForm.tsx
      shared/
        Navbar.tsx              # Logo links to / (unauth) or /dashboard (auth)
        BanninEye.tsx           # The eye component (status-reactive, animated)
        ConnectionStatus.tsx    # WebSocket connection indicator (uses BanninEye)
        GrainOverlay.tsx        # Subtle noise texture (CSS-only)
        AnimatedPage.tsx        # Page transition wrapper
        EmailBanner.tsx         # Conditional "verify your email" banner (non-blocking)
    hooks/
      useAuth.ts
      useAgentSocket.ts         # WebSocket hook for real-time data
    stores/
      dashboardStore.ts         # Zustand: current agent, cached metrics
    lib/
      api.ts                    # Typed API client
      fonts.ts                  # next/font configurations
      utils.ts                  # cn(), formatDate, formatBytes, etc.
    schemas/
      auth.ts                   # Zod schemas matching backend
      agents.ts
    types/
      index.ts                  # Shared TypeScript interfaces
  public/
    bannin-eye.svg              # Eye logo (SVG, scalable)
    bannin-eye.png              # Eye icon for notifications (192x192)
    bannin-eye-favicon.svg      # Favicon
    sw.js                       # Service worker for Web Push (handles push + notificationclick events)
  next.config.js
  tailwind.config.ts
  tsconfig.json
  package.json
  vercel.json
  .env.local.example
```

## Tailwind Config

```typescript
// tailwind.config.ts key customizations
{
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: '#040506', card: '#0a0c10', raised: '#12121a', border: '#141c28' },
        accent: { cyan: '#00d4ff', cyanGlow: 'rgba(0,212,255,0.35)' },
        status: { green: '#00ff88', amber: '#f0a500', red: '#ff4444' },
      },
      fontFamily: {
        display: ['var(--font-space-grotesk)'],
        body: ['var(--font-dm-sans)'],
        mono: ['var(--font-jetbrains-mono)'],
      },
      animation: {
        'fade-up': 'fadeUp 0.6s ease-out',
        'pulse-red': 'pulseRed 2.5s ease-in-out infinite',
        'glow-cyan': 'glowCyan 2s ease-in-out infinite',
        'eye-blink': 'eyeBlink 0.3s ease-in-out',
        'eye-open': 'eyeOpen 0.8s ease-out',
      },
    },
  },
}
```

## Vercel Configuration

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build"
}
```

## Environment Variables (.env.local.example)

```
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=ws://localhost:3001
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_VAPID_PUBLIC_KEY=your-vapid-public-key
```

## SEO & Open Graph

The landing page (`/`) must have proper metadata for link sharing:

```typescript
// src/app/page.tsx or src/app/layout.tsx
export const metadata: Metadata = {
  title: 'Bannin -- watchman for your compute',
  description: 'Monitor your machine, training runs, and AI tools from anywhere. OOM prediction, smart alerts, zero setup.',
  openGraph: {
    title: 'Bannin -- watchman for your compute',
    description: 'You hit run. You walk away. Then what?',
    url: 'https://bannin.vercel.app',
    siteName: 'Bannin',
    type: 'website',
  },
};
```

## Performance Requirements

- Lighthouse score > 90
- Fonts loaded with `display: swap` and preloaded
- Route-based code splitting (automatic with App Router)
- WebSocket messages processed without layout thrashing (batch DOM updates)
- Chart updates throttled to 1fps (not every 10s metric push)

## Accessibility

- Semantic HTML throughout
- All interactive elements keyboard accessible
- Focus management on page transitions
- `aria-live="polite"` on metric values, alert banners, connection status
- Color + text/icon for all status states (never color-only)
- `prefers-reduced-motion` respected -- disable animations, use instant transitions

## Build Verification

After generating all code:
1. Run `npm install`
2. Run `npm run build` -- fix all TypeScript and build errors
3. Verify all routes render without errors
4. Test WebSocket connection handling (connect, disconnect, reconnect)
5. Test auth flow end-to-end (register without email, register with email, login by username, login by email)
6. Verify responsive layout at 375px, 768px, 1024px, 1440px
7. Initialize git repository, create `.gitignore`, commit: `feat: Bannin Web Dashboard -- remote monitoring interface`

## Principal Engineer Review Protocol

After the build passes, conduct a full code review as if you are a principal/staff engineer at Google, Vercel, or Stripe reviewing a production frontend that real users will interact with daily. This is the quality gate. Ship nothing that would not survive this review.

### Review Process

1. Review every file, top to bottom. No skimming. No "this looks fine."
2. For each issue found, classify severity:
   - **Critical (C)**: XSS vulnerability, auth bypass, token exposure in URL/logs, broken auth flow
   - **High (H)**: Missing error state, broken accessibility, memory leak (event listener not cleaned up), unbounded state growth
   - **Medium (M)**: Type safety gap (`any` usage), missing loading state, inconsistent error handling, broken responsive layout at a key breakpoint
   - **Low (L)**: Naming inconsistency, unused import, suboptimal animation timing, minor spacing issue
3. Fix each issue individually. Do not batch fixes. Verify the fix builds clean after each.
4. After all issues are fixed, re-review from scratch. New eyes, full pass.
5. Repeat until a full review pass finds **zero issues at any severity level**. Only then is the review PASS.

### Review Checklist (Every File, Every Time)

**Security (the non-negotiable layer)**:
- [ ] No API data rendered via `dangerouslySetInnerHTML` without sanitization. All dynamic text uses JSX text nodes (auto-escaped by React).
- [ ] JWT stored in localStorage only (not cookies accessible to JS, not URL params). Cleared on logout.
- [ ] No tokens, API keys, or secrets in URL query params, console.log, or error messages shown to users.
- [ ] Auth redirect loop prevention: protected routes redirect to `/login?returnUrl=...`, login redirects back. No infinite loop if token is invalid.
- [ ] API client handles 401 by clearing auth state and redirecting. Does not retry with stale token infinitely.
- [ ] WebSocket token passed via query param over WSS (TLS) only. Token validated server-side.
- [ ] No secret values in `NEXT_PUBLIC_*` env vars (only API URL, WS URL, app URL).
- [ ] CSRF: not applicable (JWT in header, not cookie), but verify no cookie-based auth accidentally introduced.

**Type Safety**:
- [ ] No `any` type in component props, API responses, or state. Every `as` cast has a comment explaining safety.
- [ ] Zod schemas validate all form inputs before submission. Backend validation errors displayed to user.
- [ ] API client response types match actual backend response shapes. Discriminated unions for success/error.
- [ ] WebSocket message types are exhaustively handled (switch/case with default logging unknown types).
- [ ] All optional fields handled with nullish checks. No `user.email.toLowerCase()` when `email` can be null.

**Error Handling & UX Completeness**:
- [ ] Every async operation has 4 states: loading, success, error, empty. No dead ends.
- [ ] API errors displayed as user-friendly toast or inline message. Never raw JSON or "Something went wrong."
- [ ] Network failure: visible "Connection lost" indicator + automatic retry. Not silent.
- [ ] WebSocket disconnect: visible indicator with auto-reconnect. Dashboard shows stale data timestamp.
- [ ] Form validation: inline errors below fields, not just toast. Errors clear when user starts typing.
- [ ] Button loading states: disabled + spinner during async operations. No double-submit.
- [ ] Empty states: every list/table has a meaningful empty state with guidance. Not blank space.
- [ ] 404 route: custom page with navigation back to dashboard.

**Accessibility**:
- [ ] Heading hierarchy: exactly one `<h1>` per page, logical `<h2>`-`<h6>` nesting.
- [ ] All form inputs have `<label>` elements (not just placeholder text).
- [ ] All buttons have accessible names (text content or `aria-label`).
- [ ] Focus management: modal opens -> focus trapped inside. Modal closes -> focus returns to trigger.
- [ ] Keyboard navigation: Tab order logical. Enter/Space activate buttons. Escape closes modals/dropdowns.
- [ ] `aria-live="polite"` on: metric values, alert count, connection status, toast container.
- [ ] Color contrast: all text meets WCAG AA (4.5:1 for body text, 3:1 for large text). Test cyan-on-dark especially.
- [ ] Status communicated by color + text/icon. Never color alone (red/amber/green always paired with text label).
- [ ] `prefers-reduced-motion`: all Framer Motion animations wrapped in `useReducedMotion()` check.
- [ ] Images: `alt` text on all meaningful images. `alt=""` on decorative images.

**Performance**:
- [ ] No full DOM rebuilds on WebSocket message. Diff state and update only changed values.
- [ ] Zustand selectors: components subscribe to specific slices, not entire store.
- [ ] Chart re-renders throttled. Ring buffer for time-series data (max 300 points).
- [ ] No redundant API calls. Dashboard overview fetched once, then WebSocket provides updates.
- [ ] Images lazy-loaded with `next/image` where applicable.
- [ ] No `useEffect` without cleanup function when subscribing to events or setting timers.
- [ ] WebSocket reconnect uses exponential backoff (1s, 2s, 4s... max 30s). Not rapid-fire.

**Responsive Design**:
- [ ] 375px (mobile): single column, cards stack, navbar collapses to hamburger, metric cards readable.
- [ ] 768px (tablet): 2-column grid starts, chart fits.
- [ ] 1024px (small laptop): full layout visible.
- [ ] 1440px (desktop): maximum content width, comfortable spacing.
- [ ] No horizontal overflow at any breakpoint. No text truncation that hides critical data.

**State Management**:
- [ ] Auth state: single source of truth in AuthProvider. No duplicate token storage.
- [ ] Dashboard state: Zustand store with bounded collections (deque pattern, max 300 metric history points).
- [ ] WebSocket state: managed in custom hook, cleaned up on unmount. No orphaned connections.
- [ ] Form state: React Hook Form, not manual `useState` for each field. Wizard state persisted in Zustand + localStorage.
- [ ] No stale closures: useCallback/useMemo dependencies correct. No missing deps in useEffect.

**Branding Consistency**:
- [ ] Bannin eye appears in: navbar, favicon, landing hero, loading states, empty states, notification icon.
- [ ] Eye color reflects status: cyan (normal), amber (warning), red (critical), gray (offline/loading).
- [ ] "番人" kanji appears in: landing hero, footer. Not overused elsewhere.
- [ ] Consistent dark theme: no white backgrounds, no default browser styles leaking through.
- [ ] Human tone in all copy. No "Error 422" shown to users. No "null" or "undefined" visible.

### Review Report Format

After each review pass, output:

```
## Review Pass N

| # | Severity | File | Line | Issue | Fix |
|---|----------|------|------|-------|-----|
| 1 | C | LoginForm.tsx | 31 | Password visible in URL on redirect | Use POST body, not query param |
| 2 | H | MetricCard.tsx | 45 | No aria-live on metric value update | Add aria-live="polite" |

**Result**: FAIL (1C, 2H, 5M) -- fix all and re-review
```

Continue until:

```
## Review Pass N

No issues found.

**Result**: PASS
```

## Important Constraints

- No component libraries (no shadcn, no MUI, no Chakra). All UI custom-built with Tailwind.
- No AI calls from the frontend.
- Responsive -- must work on desktop (primary) and tablet/mobile.
- Every animation respects `prefers-reduced-motion`.
- Human tone in all copy. Not robotic. Not corporate. Like a friend who knows systems.
- The design must feel like Bannin -- dark, precise, alive with data. Not a generic admin template.
- Email is never required. No feature is gated behind email verification. Email is a power-up for recovery and notifications, presented as optional in all UI flows.
- The Bannin eye is the visual anchor. It replaces generic spinners, status dots, and placeholder icons throughout the interface.
