# tests/test_orchestrator_stream_ffmpeg.py
import os
import sys
import types
import shutil
from pathlib import Path

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.utils.subproc import run_streamed
from bin.utils.ffmpeg import encode_with_fallback

def test_run_streamed_echo(tmp_path):
    """Test basic streaming subprocess functionality."""
    log_path = tmp_path / "echo.log"
    rc = run_streamed(["python", "-c", "print('hello');"], log_path=str(log_path), check=True)
    assert rc == 0
    assert log_path.exists()
    assert "hello" in log_path.read_text()

def test_run_streamed_failure(tmp_path):
    """Test streaming subprocess with failure."""
    log_path = tmp_path / "failure.log"
    try:
        run_streamed(["python", "-c", "import sys; print('error'); sys.exit(1)"], 
                     log_path=str(log_path), check=True)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Command failed" in str(e)
        assert "error" in str(e)
        assert log_path.exists()

def test_strict_yt_only_gating():
    """Test strict yt-only ingestion gating."""
    # import the gating function from run_pipeline
    from bin.run_pipeline import _should_run_shared_ingestion
    mk = lambda yto: types.SimpleNamespace(yt_only=yto)
    assert _should_run_shared_ingestion(mk(False)) is True
    assert _should_run_shared_ingestion(mk(True)) is False

def test_ffmpeg_fallback_smoke(tmp_path):
    """Test FFmpeg fallback functionality."""
    if not shutil.which("ffmpeg"):
        import pytest
        pytest.skip("ffmpeg not installed")

    input_color = tmp_path / "color.mp4"
    output = tmp_path / "out.mp4"
    
    # create a tiny color source
    rc = run_streamed([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1", str(input_color)
    ], check=True)
    assert rc == 0

    # Force fallback path by passing a bogus first codec then libx264
    encode_with_fallback(
        input_path=str(input_color),
        output_path=str(output),
        codecs=["codec_does_not_exist", "libx264"],
        log_path=str(tmp_path / "encode.log"),
    )
    assert output.exists() and output.stat().st_size > 0

def test_ffmpeg_fallback_macos_preference():
    """Test that macOS prefers VideoToolbox."""
    import platform
    from bin.utils.ffmpeg import _default_codecs
    
    if platform.system().lower() == "darwin":
        codecs = _default_codecs()
        assert codecs[0] == "h264_videotoolbox"
        assert "libx264" in codecs
    else:
        codecs = _default_codecs()
        assert codecs[0] == "libx264"

def test_run_streamed_logging(tmp_path):
    """Test that run_streamed properly logs to file."""
    log_path = tmp_path / "test.log"
    
    # Test with echo=True (default)
    rc = run_streamed(["python", "-c", "print('test output')"], 
                      log_path=str(log_path), check=True)
    assert rc == 0
    assert log_path.exists()
    content = log_path.read_text()
    assert "test output" in content
    
    # Test with echo=False
    log_path2 = tmp_path / "test2.log"
    rc = run_streamed(["python", "-c", "print('silent output')"], 
                      log_path=str(log_path2), echo=False, check=True)
    assert rc == 0
    assert log_path2.exists()
    content2 = log_path2.read_text()
    assert "silent output" in content2

if __name__ == "__main__":
    # Simple test runner if pytest is not available
    print("Running orchestrator streaming and FFmpeg tests...")
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        test_run_streamed_echo(tmp_path)
        test_run_streamed_failure(tmp_path)
        test_strict_yt_only_gating()
        test_ffmpeg_fallback_macos_preference()
        test_run_streamed_logging(tmp_path)
        
        # Skip FFmpeg test if not available
        if shutil.which("ffmpeg"):
            test_ffmpeg_fallback_smoke(tmp_path)
            print("✓ FFmpeg fallback test passed")
        else:
            print("⚠ FFmpeg not available, skipping fallback test")
    
    print("All tests passed!")
