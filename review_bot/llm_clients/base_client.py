import json
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
        import requests

        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant: "

        with requests.Session() as session:
            response = session.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model_name, "prompt": full_prompt, "stream": False},
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            content = result.get("response", "")

            # Try to parse as JSON, fallback to string
            if content.startswith("{") and content.endswith("}"):
                parsed_json = json.loads(content)
                return parsed_json
            else:
                return {"response": content}


class GeminiClient(BaseLLMClient):
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        super().__init__(model_name)

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment")

        try:
            import google.genai as genai

            # Initialize client with API key
            self.client = genai.Client(api_key=api_key)
            self.model_name = model_name
        except Exception as e:
            import logging

            logging.error("Failed to initialize Gemini client: %s", str(e))
            raise

    def generate_structured_response(
        self, prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        import logging

        logger = logging.getLogger(__name__)

        full_prompt = f"{system_prompt}\n\n{prompt}"

        response = self.client.models.generate_content(
            model=self.model_name, contents=full_prompt
        )

        if not response:
            logger.error("Empty response from Gemini API")
            return {"error": "Empty response from Gemini API"}

        content = response.text if hasattr(response, "text") else str(response)

        # Try to parse as JSON, fallback to string
        if content.startswith("{") and content.endswith("}"):
            parsed_json = json.loads(content)
            return parsed_json
        else:
            return {"response": content}
