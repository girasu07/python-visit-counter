CREATE TABLE IF NOT EXISTS daily_snapshots (
 day TEXT PRIMARY KEY,
 captured_ms INTEGER NOT NULL,
 received_ms INTEGER NOT NULL,
 payload TEXT NOT NULL
);
