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
        try:
            import requests

            full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant: "

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model_name, "prompt": full_prompt, "stream": False},
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "")

                # Try to parse as JSON, fallback to string
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"response": content}
            else:
                return {"error": f"Ollama API error: {response.status_code}"}

        except Exception as e:
            return {"error": str(e)}


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
            print(f"Failed to initialize Gemini client: {e}")
            raise

    def generate_structured_response(
        self, prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}"

            response = self.client.models.generate_content(
                model=self.model_name, contents=full_prompt
            )

            content = response.text if hasattr(response, "text") else str(response)

            # Try to parse as JSON, fallback to string
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"response": content}

        except Exception as e:
            return {"error": str(e)}
