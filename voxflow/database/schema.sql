CREATE TABLE users (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(320) UNIQUE NOT NULL,
  password_hash VARCHAR(500) NOT NULL,
  plan VARCHAR(32) NOT NULL DEFAULT 'free',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(64) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE channels (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  niche VARCHAR(100) NOT NULL,
  language VARCHAR(16) NOT NULL DEFAULT 'en-US',
  videos_per_day INTEGER NOT NULL DEFAULT 1 CHECK (videos_per_day BETWEEN 1 AND 10),
  platform VARCHAR(32) NOT NULL DEFAULT 'tiktok',
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX idx_channels_user_id ON channels(user_id);

-- Planned production tables for the next milestone:
-- videos, video_assets, publication_jobs, analytics_daily, subscriptions and usage_events.
