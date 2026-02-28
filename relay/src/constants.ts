export const VERSION = "0.1.0";

// Resource bounds
export const MAX_SNAPSHOTS_PER_AGENT = 8640;
export const MAX_EVENTS_PER_AGENT = 100_000;
export const MAX_ALERTS_PER_AGENT = 10_000;
export const MAX_AGENTS_PER_USER = 20;
export const MAX_PUSH_SUBS_PER_USER = 10;

// WebSocket
export const HEARTBEAT_TIMEOUT_MS = 60_000;
export const WS_PING_INTERVAL_MS = 30_000;
export const MAX_WS_MESSAGE_SIZE = 1_048_576; // 1 MB

// Training stop
export const TRAINING_STOP_GRACE_MS = 30_000;

// Pruning
export const SNAPSHOT_PRUNE_INTERVAL_MS = 3_600_000; // 1 hour

// Pagination
export const EVENTS_PAGE_LIMIT = 100;
export const DEFAULT_PAGE_LIMIT = 50;

// Auth
export const BCRYPT_ROUNDS = 12;
export const VERIFY_TOKEN_EXPIRY_HOURS = 24;
export const RESET_TOKEN_EXPIRY_HOURS = 1;
export const KEY_PREFIX_LENGTH = 16;

// Username
export const USERNAME_MIN_LENGTH = 3;
export const USERNAME_MAX_LENGTH = 30;
