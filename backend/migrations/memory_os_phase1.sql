-- Phase 1: Memory OS Foundation

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns to existing tables
ALTER TABLE staff_memories ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_staff_memories_embedding ON staff_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_embedding ON knowledge_items USING hnsw (embedding vector_cosine_ops);

-- New table: staff_identity_memories
CREATE TABLE IF NOT EXISTS staff_identity_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rental_id UUID NOT NULL REFERENCES rental_instances(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'preference',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    source TEXT NOT NULL DEFAULT 'extracted',
    confirmed BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_identity_rental ON staff_identity_memories(rental_id);

-- New table: staff_episodes
CREATE TABLE IF NOT EXISTS staff_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rental_id UUID NOT NULL REFERENCES rental_instances(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'interaction',
    actor_id TEXT,
    summary TEXT NOT NULL,
    outcome TEXT,
    sentiment TEXT,
    importance REAL NOT NULL DEFAULT 0.5,
    business_impact REAL,
    embedding vector(1536),
    source_event_id TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_episodes_rental_group ON staff_episodes(rental_id, group_id);
CREATE INDEX IF NOT EXISTS idx_episodes_embedding ON staff_episodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_episodes_importance ON staff_episodes(importance DESC);
