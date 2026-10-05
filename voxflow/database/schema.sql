CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE workspaces (
  id UUID PRIMARY KEY,
  owner_user_id UUID NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE channels (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  niche TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en-US',
  videos_per_day INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE social_accounts (
  id UUID PRIMARY KEY,
  channel_id UUID NOT NULL REFERENCES channels(id),
  provider TEXT NOT NULL,
  external_account_id TEXT,
  handle TEXT,
  status TEXT NOT NULL DEFAULT 'connected',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE videos (
  id UUID PRIMARY KEY,
  channel_id UUID NOT NULL REFERENCES channels(id),
  topic TEXT NOT NULL,
  title TEXT,
  script TEXT,
  language TEXT NOT NULL,
  duration_target INTEGER,
  status TEXT NOT NULL DEFAULT 'planned',
  output_url TEXT,
  scheduled_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE video_assets (
  id UUID PRIMARY KEY,
  video_id UUID NOT NULL REFERENCES videos(id),
  source_url TEXT NOT NULL,
  source_name TEXT,
  license TEXT,
  media_type TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE publication_jobs (
  id UUID PRIMARY KEY,
  video_id UUID NOT NULL REFERENCES videos(id),
  provider TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  external_post_id TEXT,
  external_url TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analytics_daily (
  id UUID PRIMARY KEY,
  channel_id UUID NOT NULL REFERENCES channels(id),
  provider TEXT NOT NULL,
  day DATE NOT NULL,
  views BIGINT NOT NULL DEFAULT 0,
  likes BIGINT NOT NULL DEFAULT 0,
  comments BIGINT NOT NULL DEFAULT 0,
  shares BIGINT NOT NULL DEFAULT 0,
  followers_delta BIGINT NOT NULL DEFAULT 0,
  UNIQUE(channel_id, provider, day)
);
