"""
tests/test_agents.py
---------------------
Unit tests for the core LangGraph agents (Director, Hook Analyst, Cinematographer).
LLM calls are mocked at the ChatGroq layer so tests are deterministic and free.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ──────────────────────────────────────────────────────────────
# Shared state fixtures
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def base_state():
    return {
        "job_id": "unit-test-job-001",
        "telegram_chat_id": "12345",
        "raw_prompt": "A samurai battles demons at dusk",
        "memory_context": "None",
        "characters": [],
        "scenes": [],
        "current_agent": "START",
        "validation_failures": 0,
        "last_error": None,
        "running_cost_usd": 0.0,
    }


@pytest.fixture
def state_with_scenes(base_state):
    base_state["characters"] = [
        {"id": "char_1", "name": "Kira", "physical_description": "tall warrior", "outfit": "black armor", "locked_face_url": None, "voice_id": None}
    ]
    base_state["scenes"] = [
        {
            "scene_number": 1,
            "script_text": "Kira steps into a moonlit courtyard, a demon shadow looms behind.",
            "camera_angle": None,
            "lighting_prompt": None,
            "hook_score": None,
            "keyframe_url": None,
            "video_url": None,
            "audio_url": None,
        },
        {
            "scene_number": 2,
            "script_text": "Kira draws her blade with blinding speed.",
            "camera_angle": None,
            "lighting_prompt": None,
            "hook_score": None,
            "keyframe_url": None,
            "video_url": None,
            "audio_url": None,
        },
    ]
    return base_state


# ──────────────────────────────────────────────────────────────
# Director Agent Tests
# ──────────────────────────────────────────────────────────────
class TestDirectorAgent:
    @pytest.mark.asyncio
    async def test_director_happy_path(self, base_state):
        """Director should populate characters and scenes in state."""
        from pydantic import BaseModel
        from typing import List

        class MockChar(BaseModel):
            id: str = "char_1"
            name: str = "Kira"
            physical_description: str = "Tall warrior"
            outfit: str = "Black armor"

        class MockScene(BaseModel):
            scene_number: int = 1
            script_text: str = "Opening scene text"

        class MockOutput(BaseModel):
            characters: List[MockChar] = [MockChar()]
            scenes: List[MockScene] = [MockScene()]

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=MockOutput())

        with patch("backend.agents.director.ChatGroq", return_value=mock_llm):
            from backend.agents.director import agent_director
            result = await agent_director(base_state)

        assert result["current_agent"] == "cinematographer"
        assert len(result["characters"]) == 1
        assert len(result["scenes"]) == 1

    @pytest.mark.asyncio
    async def test_director_llm_failure_raises(self, base_state):
        """After retries, director records the error and returns state (no uncaught raise)."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=Exception("Groq 503"))

        with patch("backend.agents.director.ChatGroq", return_value=mock_llm):
            from backend.agents.director import agent_director
            result = await agent_director(base_state)

        assert "RetryError" in (result.get("last_error") or "") or "Groq 503" in (result.get("last_error") or "")
        assert result.get("validation_failures", 0) >= 1


# ──────────────────────────────────────────────────────────────
# Hook Analyst Agent Tests
# ──────────────────────────────────────────────────────────────
class TestHookAnalystAgent:
    @pytest.mark.asyncio
    async def test_hook_above_threshold_keeps_scene(self, state_with_scenes):
        """A score ≥ 7 should keep the original script text unchanged."""
        from pydantic import BaseModel

        class MockHook(BaseModel):
            score: int = 8
            critique: str = "Strong opening"
            improved_script_text: str = "SHOULD NOT BE USED"

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=MockHook())

        with patch("backend.agents.hook_analyst.ChatGroq", return_value=mock_llm):
            from backend.agents.hook_analyst import agent_hook_analyst
            result = await agent_hook_analyst(state_with_scenes)

        scene_1 = next(s for s in result["scenes"] if s["scene_number"] == 1)
        assert scene_1["hook_score"] == 8
        # Original text should be unchanged
        assert "courtyard" in scene_1["script_text"]

    @pytest.mark.asyncio
    async def test_hook_below_threshold_rewrites_scene(self, state_with_scenes):
        """A score < 7 should replace Scene 1's script_text."""
        from pydantic import BaseModel

        class MockHook(BaseModel):
            score: int = 4
            critique: str = "Too slow"
            improved_script_text: str = "REWRITTEN: Kira explodes through the gate in slow motion."

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=MockHook())

        with patch("backend.agents.hook_analyst.ChatGroq", return_value=mock_llm):
            from backend.agents.hook_analyst import agent_hook_analyst
            result = await agent_hook_analyst(state_with_scenes)

        scene_1 = next(s for s in result["scenes"] if s["scene_number"] == 1)
        assert scene_1["hook_score"] == 4
        assert "REWRITTEN" in scene_1["script_text"]

    @pytest.mark.asyncio
    async def test_hook_no_scene_1_returns_safely(self, base_state):
        """If there are no scenes in state, the agent should return without crashing."""
        from backend.agents.hook_analyst import agent_hook_analyst
        result = await agent_hook_analyst(base_state)
        assert result["scenes"] == []


# ──────────────────────────────────────────────────────────────
# Cinematographer Agent Tests
# ──────────────────────────────────────────────────────────────
class TestCinematographerAgent:
    @pytest.mark.asyncio
    async def test_cinematographer_skips_without_api_key(self, state_with_scenes):
        """If GROQ_API_KEY is missing, agent skips and passes state through."""
        with patch.dict("os.environ", {}, clear=True):
            from backend.agents.cinematographer import agent_cinematographer
            result = await agent_cinematographer(state_with_scenes)
        assert result["current_agent"] == "Hook Analyst"
        # Camera angles should remain None
        assert result["scenes"][0]["camera_angle"] is None

    @pytest.mark.asyncio
    async def test_cinematographer_populates_shots(self, state_with_scenes):
        """When API key is present, camera_angle and lighting must be populated."""
        from pydantic import BaseModel
        from typing import List

        class MockShot(BaseModel):
            scene_number: int
            camera_angle: str
            lighting_prompt: str

        class MockOutput(BaseModel):
            shots: List[MockShot] = [
                MockShot(scene_number=1, camera_angle="Low angle, 24mm", lighting_prompt="Moonlit chiaroscuro"),
                MockShot(scene_number=2, camera_angle="Tracking shot", lighting_prompt="Hard rim light"),
            ]

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=MockOutput())

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("backend.agents.cinematographer.ChatGroq", return_value=mock_llm):
                from backend.agents.cinematographer import agent_cinematographer
                result = await agent_cinematographer(state_with_scenes)

        scene_1 = next(s for s in result["scenes"] if s["scene_number"] == 1)
        assert scene_1["camera_angle"] == "Low angle, 24mm"
        assert scene_1["lighting_prompt"] == "Moonlit chiaroscuro"
        assert result["current_agent"] == "hook_analyst"


# ──────────────────────────────────────────────────────────────
# Vocal Synthesizer Agent Tests
# ──────────────────────────────────────────────────────────────
class TestVocalSynthesizerAgent:
    @pytest.mark.asyncio
    async def test_vocal_synthesizer_fallback_to_edge_tts(self, state_with_scenes):
        """Agent should use Edge-TTS if ElevenLabs key is missing."""
        mock_supabase = MagicMock()
        mock_supabase.storage.from_.return_value.get_public_url.return_value = "https://audio.url/test.mp3"

        # Mock edge_tts.Communicate
        class MockCommunicate:
            def __init__(self, text, voice): pass
            async def stream(self):
                yield {"type": "audio", "data": b"fake-audio"}

        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}):
            with patch("backend.agents.vocal_synthesizer.get_supabase_client", return_value=mock_supabase):
                with patch("backend.agents.vocal_synthesizer.edge_tts.Communicate", MockCommunicate):
                    from backend.agents.vocal_synthesizer import agent_vocal_synthesizer
                    result = await agent_vocal_synthesizer(state_with_scenes)

        assert result["current_agent"] == "lip_sync"
        assert result["scenes"][0]["audio_url"] == "https://audio.url/test.mp3"
        assert result["scenes"][1]["audio_url"] == "https://audio.url/test.mp3"
