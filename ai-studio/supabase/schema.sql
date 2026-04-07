-- Enable pgvector extension for Agent 11 Cross-Episode Memory
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. JOBS TABLE: The master record for a single episode pipeline
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, RUNNING, HITL_PAUSE, COMPLETED, FAILED
    pipeline_stage TEXT NOT NULL DEFAULT 'INITIALIZED',
    
    -- Telemetry & UX
    telegram_chat_id TEXT,
    telegram_console_message_id TEXT,
    
    -- Budgeting
    cost_usd NUMERIC(10, 4) DEFAULT 0.0000,
    
    -- DLQ & Error Handling
    error_log TEXT,
    retries_used INT DEFAULT 0,
    
    -- Result
    video_url TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 2. CHARACTERS TABLE: Locked physiological traits and Voice IDs
CREATE TABLE characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    
    -- LLM Descriptions
    physical_description TEXT NOT NULL,
    outfit TEXT,
    
    -- Identity Locking
    locked_face_url TEXT,
    voice_id TEXT, -- Kokoro TTS Voice profile
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 3. SCENES TABLE: The granular building blocks of the episode
CREATE TABLE scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    scene_number INT NOT NULL,
    
    -- Agent 1 & 2 Drafts
    script_text TEXT,
    camera_angle TEXT,
    lighting_prompt TEXT,
    
    -- Agent 3 Metrics
    hook_score INT,
    
    -- Cloud Asset URLs (S3)
    keyframe_url TEXT,
    audio_url TEXT,
    lip_sync_url TEXT, -- Agent 7 output
    motion_url TEXT,   -- Agent 8 output
    video_url TEXT,    -- Final scene video
    
    -- Internal State
    status TEXT DEFAULT 'PENDING',
    pipeline_stage TEXT DEFAULT 'DIRECTOR_DRAFTING',
    
    -- Validation (Agent 5 & 8)
    vision_qa_score NUMERIC(3, 2),
    qa_notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 4. EPISODE MEMORY LEDGER (Agent 11): Persistence across the season
CREATE TABLE memory_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    series_name TEXT NOT NULL, -- Logical grouping (e.g., 'Cyberpunk_Detective_S1')
    
    -- The core memory content
    content TEXT NOT NULL,
    
    -- pgvector embedding for semantic retrieval
    embedding vector(1536), 
    
    -- Structured Metadata
    entity_type TEXT, -- e.g., 'CHARACTER_DEATH', 'PROP_LOCATION', 'WORLD_BUILDING'
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Update Triggers for automatically updating `updated_at` columns
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_jobs_modtime BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_scenes_modtime BEFORE UPDATE ON scenes FOR EACH ROW EXECUTE FUNCTION update_modified_column();
