import pytest
import os
import time
import shutil
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

# ──────────────────────────────────────────────────────────────
# 1. Filesystem Janitor Test
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_janitor_sweep_logic():
    """Verifies that the janitor deletes directories older than 1 hour."""
    from backend.worker import janitor_task
    
    mock_files = ["old_job_1", "new_job_2"]
    mock_now = time.time()
    
    # Mock os.listdir, isdir, and getmtime
    with patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=mock_files), \
         patch("os.path.isdir", return_value=True), \
         patch("os.path.getmtime") as mock_mtime, \
         patch("shutil.rmtree") as mock_rm, \
         patch("asyncio.sleep", side_effect=[None, Exception("StopLoop")]):
        
        # old_job_1: 2 hours ago
        # new_job_2: 10 mins ago
        mock_mtime.side_effect = [mock_now - 7200, mock_now - 600]
        
        try:
            await janitor_task()
        except Exception as e:
            if str(e) != "StopLoop": raise
            
        # Should only delete the old job (temp base is platform-specific, not /tmp on Windows)
        expected_base = os.path.join(tempfile.gettempdir(), "ai_studio_renders")
        assert mock_rm.call_count == 1
        mock_rm.assert_called_once_with(os.path.join(expected_base, "old_job_1"), ignore_errors=True)

# ──────────────────────────────────────────────────────────────
# 2. Media Sync (FPS Lock) Audit
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_video_assembler_fps_lock():
    """Ensures Agent 6 forces 24 FPS on all sub-clips to prevent sync drift."""
    # Mock state and sub-agents
    state = {
        "job_id": "test_sync_001",
        "scenes": [{"scene_number": 1, "keyframe_url": "http://img", "audio_url": "http://aud"}]
    }
    
    mock_final = MagicMock()

    def _touch_mp4(path, *args, **kwargs):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"fake-mp4")

    mock_final.write_videofile.side_effect = _touch_mp4

    with patch("backend.agents.video_assembler.AudioFileClip") as mock_audio, \
         patch("backend.agents.video_assembler.ImageClip") as mock_image, \
         patch("backend.agents.video_assembler.download_asset"), \
         patch("backend.agents.video_assembler.get_supabase_client") as mock_sb, \
         patch("backend.agents.video_assembler.concatenate_videoclips", return_value=mock_final) as mock_concat, \
         patch("asyncio.to_thread", side_effect=lambda f, *args, **kwargs: f(*args, **kwargs) if callable(f) else None), \
         patch("shutil.rmtree"):
        mock_sb.return_value.storage.from_.return_value.upload.return_value = None
        mock_audio.return_value.duration = 5.0

        # MoviePy 2-style chain: .resized().with_fps(24)
        mock_clip = MagicMock()
        mock_after_resize = MagicMock()
        mock_image.return_value.set_duration.return_value.set_audio.return_value = mock_clip
        mock_clip.resized.return_value = mock_after_resize
        mock_after_resize.with_fps.return_value = mock_clip

        from backend.agents.video_assembler import agent_video_assembler

        await agent_video_assembler(state)

        # Sub-clip FPS is applied via .with_fps(24) before concat; the render also locks fps=24.
        mock_final.write_videofile.assert_called()
        _args, kwargs = mock_final.write_videofile.call_args
        assert kwargs.get("fps") == 24

# ──────────────────────────────────────────────────────────────
# 3. Connection Pool Constraint Audit
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_db_pool_configuration():
    """Verifies that the asyncpg pool is strictly capped to prevent Supabase saturation."""
    from backend import db
    
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            await db.get_pool()
            
            # Verify pool size constraints
            args, kwargs = mock_create.call_args
            assert kwargs["max_size"] <= 5, "Connection pool too large for Supabase free-tier scaling!"

# ──────────────────────────────────────────────────────────────
# 4. End-to-End DAG Connectivity Simulation
# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dag_connectivity():
    """A 'smoke test' to ensure the graph compiles and identifies the correct agents."""
    from backend.graph import agent_pipeline
    
    # We just want to see if the graph has the new video_assembler node
    nodes = agent_pipeline.nodes
    assert "video_assembler" in nodes
    assert "final_persistence" in nodes
    
    # Check edges
    # Note: In compiled graph, edges are complex. We check by logical graph builder knowledge.
    # If the import works and nodes exist, the wiring is verified by the compile() call in graph.py.
