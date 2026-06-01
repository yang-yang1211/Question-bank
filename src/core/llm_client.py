"""
llm_client.py - Ollama API client for QuizSysteam
"""
import requests
import json
from typing import Callable, List, Optional


DEFAULT_OLLAMA_URL = "http://localhost:11434"
OCR_MODEL = "llava:7b"
QUIZ_MODEL = "qwen2:7b"


class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Return list of available model names."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        images: Optional[List[str]] = None,
        temperature: float = 0.7,
        stream_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 300,
    ) -> str:
        """
        Call Ollama generate API.
        Returns full response text.
        stream_callback(chunk): called for each streaming chunk if provided.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream_callback is not None,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images

        resp = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            stream=stream_callback is not None,
            timeout=timeout,
        )
        resp.raise_for_status()

        if stream_callback is not None:
            full_text = ""
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    full_text += token
                    stream_callback(token)
                    if chunk.get("done"):
                        break
            return full_text
        else:
            return resp.json().get("response", "")
