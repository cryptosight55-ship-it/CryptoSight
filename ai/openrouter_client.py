"""
Minimal OpenRouter client. OpenRouter exposes an OpenAI-compatible API, so
this is just a small wrapper over `httpx` rather than pulling in the full
OpenAI SDK for one endpoint.

Swap models by changing OPENROUTER_MODEL in the environment -- nothing
else in the codebase needs to change. Start with a `:free` model for
testing; move to a paid model later by changing that one env var.
Free model IDs on OpenRouter rotate frequently (providers add/remove
them without notice) -- check https://openrouter.ai/models before
deploying and if you start seeing 404s on the model ID.
"""

import json
import logging
from typing import List, Dict, Optional

import httpx

from config.settings import config

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    pass


class OpenRouterClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.model = model or config.OPENROUTER_MODEL
        self.base_url = config.OPENROUTER_BASE_URL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format_json: bool = False,
        timeout: float = 30.0,
    ) -> str:
        """
        Send a chat completion request. Returns the assistant's text content.
        Raises OpenRouterError on failure (missing key, HTTP error, bad shape).
        """
        if not self.is_configured():
            raise OpenRouterError(
                "OPENROUTER_API_KEY is not set. Add it to your environment "
                "(Render dashboard, or .env locally) to enable AI features."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter uses these for its public leaderboard attribution;
            # optional but recommended.
            "HTTP-Referer": config.AI_SITE_URL,
            "X-Title": config.AI_SITE_NAME,
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} {e.response.text}")
            raise OpenRouterError(
                f"OpenRouter request failed ({e.response.status_code}). "
                f"If this is a 404, the model ID '{self.model}' may have been "
                f"delisted -- check https://openrouter.ai/models for a current one."
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter connection error: {e}")
            raise OpenRouterError(f"Could not reach OpenRouter: {e}") from e

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from e

        if content is None:
            # Some free models (reasoning models, refusals, certain
            # routed models under openrouter/free) return a present but
            # null content field instead of omitting it -- this is what
            # crashed a scan with 'NoneType' has no attribute 'strip' in
            # ai/signal_explainer.py before this check existed. Treat it
            # as a proper OpenRouterError so callers that already handle
            # that (like explain_signal) degrade gracefully instead.
            raise OpenRouterError(f"OpenRouter returned null content: {data}")

        return content

    def chat_json(self, messages: List[Dict[str, str]], **kwargs) -> dict:
        """Same as chat(), but parses the response as JSON. Raises OpenRouterError on bad JSON."""
        text = self.chat(messages, response_format_json=True, **kwargs)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise OpenRouterError(f"AI did not return valid JSON: {text[:500]}") from e


openrouter_client = OpenRouterClient()
