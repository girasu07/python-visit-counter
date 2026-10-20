-- Preserve the legacy table; its source gate is unknown, so do not include it in totals.
CREATE TABLE IF NOT EXISTS gate_snapshots (
 day TEXT NOT NULL,
 gate_id TEXT NOT NULL CHECK(gate_id IN ('gate-1','gate-2')),
 captured_ms INTEGER NOT NULL,
 received_ms INTEGER NOT NULL,
 payload TEXT NOT NULL,
 PRIMARY KEY(day,gate_id)
);
