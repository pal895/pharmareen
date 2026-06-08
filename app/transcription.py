from __future__ import annotations

import mimetypes

from openai import OpenAI

from app.config import Settings
from app.ai import log_ai_call


class TranscriptionUnavailableError(RuntimeError):
    pass


PHARMACY_TRANSCRIPTION_PROMPT = (
    "Kenyan pharmacy voice note. Listen for medicine names and short sale words. "
    "Common medicines include Panadol, Glucose, ORS, Cetirizine, Piriton, Amoxyl, "
    "Amoxicillin, Paracetamol, Insulin, Antacid, Cough Syrup, WaterGuard, PEP Lime Cordial. "
    "Swahili numbers: moja=1, mbili=2, tatu=3, nne=4, tano=5, sita=6, saba=7, nane=8, tisa=9, kumi=10. "
    "Payments: cash, M-Pesa, mpesa, credit, mixed. Keep the transcript short."
)


class TranscriptionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    @property
    def is_available(self) -> bool:
        return bool(self.settings.enable_voice_input and self.settings.openai_api_key and self.client)

    def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
        if not self.settings.enable_voice_input:
            raise TranscriptionUnavailableError("Voice notes are not enabled yet. Please type: Panadol 2")
        if not self.client:
            raise TranscriptionUnavailableError(
                "Voice notes need OPENAI_API_KEY. Please type it like: Panadol 2"
            )

        clean_content_type = (content_type or "audio/ogg").split(";")[0].strip()
        extension = mimetypes.guess_extension(clean_content_type) or ".ogg"
        filename = f"voice-note{extension}"

        log_ai_call("voice_transcription", "audio/transcriptions", "voice note transcription")
        result = self.client.audio.transcriptions.create(
            model=self.settings.openai_transcription_model,
            file=(filename, audio_bytes, clean_content_type),
            response_format="text",
            prompt=PHARMACY_TRANSCRIPTION_PROMPT,
        )
        if isinstance(result, str):
            return result.strip()
        return str(getattr(result, "text", "")).strip()
