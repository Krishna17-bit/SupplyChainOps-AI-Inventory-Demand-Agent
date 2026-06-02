from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AIResponse:
    ok: bool
    text: str

class AIReasoningClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro").strip() or "gemini-2.5-pro"
        self.configured = bool(self.api_key)
        self.status_help = (
            "AI narrative mode is available." if self.configured else
            "Running deterministic local analytics. Add an API key in .env to enable narrative reasoning."
        )
        self._model = None
        if self.configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(self.model_name)
            except Exception:
                self.configured = False
                self.status_help = "AI narrative mode could not initialize. Local analytics still work."

    def generate(self, prompt: str) -> AIResponse:
        if not self.configured or self._model is None:
            return AIResponse(False, "AI narrative mode is not configured. Local analytics are available.")
        try:
            response = self._model.generate_content(prompt)
            return AIResponse(True, getattr(response, "text", "") or "")
        except Exception as exc:
            return AIResponse(False, f"AI narrative generation failed safely: {exc}")
