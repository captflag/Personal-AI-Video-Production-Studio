"""
backend/tests/test_agents_v2.py
------------------------------
Unit tests for the new Lip Sync Specialist (Agent 7) and Video Alchemist (Agent 8).
Mocks external API calls (HF, FAL, Supabase) to ensure deterministic results.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from backend.state import UniversalGraphState

# ──────────────────────────────────────────────────────────────
# Shared Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def base_state():
    return {
        "job_id": "test-job-v2-001",
        "telegram_chat_id": "123456",
        "raw_prompt": "A cyberpunk samurai in a rainy alley",
        "characters": [
            {"id": "char_1", "name": "Kano", "physical_description": "samurai"}
        ],
        "scenes": [
            {
                "scene_number": 1,
                "script_text": "Kano steps into the light.",
                "keyframe_url": "https://example.com/keyframe1.png",
                "audio_url": "https://example.com/audio1.mp3",
                "status": "ASSEMBLING"
            }
        ],
        "current_agent": "lip_sync",
        "pipeline_stage": "AUDIO_GENERATED"
    }

# ──────────────────────────────────────────────────────────────
# Lip Sync Agent Tests
# ──────────────────────────────────────────────────────────────

class TestLipSyncAgent:
    @pytest.mark.asyncio
    @patch("backend.agents.lip_sync_agent.sync_pipeline_state", new_callable=AsyncMock)
    async def test_lip_sync_success(self, mock_sync, base_state):
        from backend.agents.lip_sync_agent import agent_lip_sync
        
        with patch.dict("os.environ", {"HUGGINGFACE_API_KEY": "fake-token"}):
            result = await agent_lip_sync(base_state)
            
        assert result["pipeline_stage"] == "LIP_SYNC_COMPLETED"
        assert result["scenes"][0]["status"] == "SYNCHRONIZED"
        assert result["scenes"][0]["lip_sync_video_url"] == "https://example.com/keyframe1.png"
        assert mock_sync.call_count >= 2 # Heartbeat + Completion

    @pytest.mark.asyncio
    async def test_lip_sync_skips_without_token(self, base_state):
        from backend.agents.lip_sync_agent import agent_lip_sync
        
        with patch.dict("os.environ", {"HUGGINGFACE_API_KEY": ""}, clear=True):
            result = await agent_lip_sync(base_state)
            
        assert "LIP_SYNC_COMPLETED" not in result.get("pipeline_stage", "")
        # Status should remain as it was
        assert result["scenes"][0]["status"] == "ASSEMBLING"

# ──────────────────────────────────────────────────────────────
# Video Alchemist Agent Tests
# ──────────────────────────────────────────────────────────────

class TestVideoAlchemistAgent:
    @pytest.mark.asyncio
    @patch("backend.agents.video_alchemist.get_supabase_client")
    @patch("backend.agents.video_alchemist.sync_pipeline_state", new_callable=AsyncMock)
    @patch("backend.agents.video_alchemist.generate_static_fallback")
    async def test_video_alchemist_local_fallback(self, mock_fallback, mock_sync, mock_supabase, base_state):
        from backend.agents.video_alchemist import agent_video_alchemist
        
        # Mocks
        mock_fallback.return_value = b"fake-video-bytes"
        mock_db = MagicMock()
        mock_supabase.return_value = mock_db
        mock_db.storage.from_.return_value.get_public_url.return_value = "https://example.com/motion1.mp4"
        
        # Ensure external providers fail/are disabled
        with patch.dict("os.environ", {"FAL_KEY": ""}):
            result = await agent_video_alchemist(base_state)
            
        assert result["current_agent"] == "vision_qa"
        assert result["scenes"][0]["motion_video_url"] == "https://example.com/motion1.mp4"
        assert result["scenes"][0]["motion_method"] == "CINEMATIC_ENGINE_LOCAL"
        assert mock_fallback.called

    def test_cubic_ease_in_out(self):
        from backend.agents.video_alchemist import cubic_ease_in_out
        assert cubic_ease_in_out(0) == 0
        assert cubic_ease_in_out(1) == 1
        assert 0 < cubic_ease_in_out(0.5) < 1

# ──────────────────────────────────────────────────────────────
# Precision Sync Utility Tests (utils_sync.py)
# ──────────────────────────────────────────────────────────────

class TestUtilsSync:
    @pytest.mark.asyncio
    @patch("backend.utils_sync.get_supabase_client")
    async def test_sync_pipeline_state_updates_db(self, mock_supabase, base_state):
        from backend.utils_sync import sync_pipeline_state
        
        mock_db = MagicMock()
        mock_supabase.return_value = mock_db
        
        await sync_pipeline_state("test-job", base_state, "TEST_STAGE", "Progressing...")
        
        # Check if jobs table was updated
        mock_db.table.assert_any_call("jobs")
        # Check if scenes table was updated (since scene 1 has a keyframe_url)
        mock_db.table.assert_any_call("scenes")
