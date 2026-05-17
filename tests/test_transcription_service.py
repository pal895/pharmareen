from __future__ import annotations



from app.ai import AI_USAGE_LOG
from app.config import Settings
from app.transcription import TranscriptionService


class _FakeTranscriptions:
    def create(self, **kwargs):
        assert kwargs["model"]
        assert kwargs["response_format"] == "text"
        filename, audio_bytes, content_type = kwargs["file"]
        assert filename.startswith("voice-note")
        assert audio_bytes == b"voice bytes"
        assert content_type == "audio/ogg"
        return "Panadol mbili cash"


class _FakeAudio:
    transcriptions = _FakeTranscriptions()


class _FakeOpenAIClient:
    audio = _FakeAudio()


def test_transcription_service_logs_voice_ai_usage():
    AI_USAGE_LOG.clear()
    service = TranscriptionService(Settings(_env_file=None, enable_voice_input=True, openai_api_key="test-key"))
    service.client = _FakeOpenAIClient()

    transcript = service.transcribe_audio(b"voice bytes", "audio/ogg")

    assert transcript == "Panadol mbili cash"
    assert AI_USAGE_LOG[-1]["reason"] == "voice_transcription"
    assert AI_USAGE_LOG[-1]["route"] == "audio/transcriptions"
