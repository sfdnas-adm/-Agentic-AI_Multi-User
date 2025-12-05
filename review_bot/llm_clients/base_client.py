import os
from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    """Base class for LLM clients with structured output"""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def generate_structured_response(
        self, prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        """Generate structured JSON response from LLM"""
        pass


class OllamaClient(BaseLLMClient):
    def __init__(self, model_name: str = "llama3.2"):
        super().__init__(model_name)
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    def generate_structured_response(
        self, prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        import logging

        import requests

        logger = logging.getLogger(__name__)

        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant: "
        logger.info(
            "Sending to Ollama API (length: %d): %s...",
            len(full_prompt),
            full_prompt[:200],
        )

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model_name, "prompt": full_prompt, "stream": False},
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(
                "Ollama API error: %d - %s", response.status_code, response.text
            )
            return {"response": f"Error: Ollama API returned {response.status_code}"}

        result = response.json()
        content = result.get("response", "")
        logger.info(
            "Ollama API response (length: %d): %s...", len(content), content[:200]
        )

        return {"response": content}


class GeminiClient(BaseLLMClient):
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        super().__init__(model_name)
        import logging

        logger = logging.getLogger(__name__)

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment")
            raise ValueError("GEMINI_API_KEY must be set in environment")

        import google.genai as genai

        self.client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized with model: %s", model_name)

    def generate_structured_response(
        self, prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        import logging

        logger = logging.getLogger(__name__)

        full_prompt = f"{system_prompt}\n\n{prompt}"
        logger.info(
            "Sending to Gemini API (length: %d): %s...",
            len(full_prompt),
            full_prompt[:200],
        )

        response = self.client.models.generate_content(
            model=self.model_name, contents=[{"parts": [{"text": full_prompt}]}]
        )

        if not response or not response.candidates:
            logger.error("Empty response from Gemini API")
            return {"response": "Error: Empty response from Gemini API"}

        content = response.candidates[0].content.parts[0].text
        logger.info(
            "Gemini API response (length: %d): %s...", len(content), content[:200]
        )

        return {"response": content}
