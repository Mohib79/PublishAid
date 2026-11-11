"""
Gemini LLM Client for Guideline Extraction using google-genai SDK.
Reference: Guideline Extraction Plan Section 7.3, 10.9 (GE-LLM).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.services.guidelines.llm.base import (
    BaseLLMClient,
    Finding,
    LLMExtractResult,
    LLMError,
    WHITELISTED_PATHS,
)

logger = logging.getLogger(__name__)

# Default Gemini model for extraction
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def load_prompt_template(version: str = "v1") -> tuple[str, str]:
    """Loads versioned prompt template (system and user instructions)."""
    current_dir = os.path.dirname(os.path.dirname(__file__))
    prompt_file = os.path.join(current_dir, "prompts", f"{version}.txt")
    if not os.path.isfile(prompt_file):
        raise LLMError("LLM_CONFIG_ERROR", f"Prompt template '{version}' not found at {prompt_file}")

    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("USER\n", 1)
    system_text = parts[0].replace("SYSTEM\n", "").strip()
    user_template = parts[1].strip() if len(parts) > 1 else "{chunk_text}"
    return system_text, user_template


class GeminiLLMClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        prompt_version: str = "v1",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.prompt_version = prompt_version

        self.system_prompt, self.user_template = load_prompt_template(self.prompt_version)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise LLMError(
                "LLM_CONFIG_ERROR",
                "GEMINI_API_KEY environment variable is not set. Extraction cannot proceed without a valid API key.",
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def extract_findings(
        self,
        chunk_text: str,
        heading_path: str = "",
        repair_context: str | None = None,
    ) -> LLMExtractResult:
        client = self._get_client()

        # Sanitize guidelines delimiter to prevent tag breakout (GE-INJ-03)
        safe_chunk = chunk_text.replace("</guidelines>", "&lt;/guidelines&gt;")
        
        user_prompt = self.user_template.format(
            heading_path=f"Heading: {heading_path}\n" if heading_path else "",
            chunk_text=safe_chunk,
        )

        if repair_context:
            user_prompt += f"\n\nPrevious attempt failed with error:\n{repair_context}\nPlease return valid JSON."

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
        )

        # Retry logic: rate limits (429) and 5xx get exponential backoff with jitter
        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Run synchronous client call in threadpool to avoid blocking event loop
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.model_name,
                    contents=user_prompt,
                    config=config,
                )
                break
            except APIError as e:
                last_error = e
                status_code = getattr(e, "code", None)
                if status_code in (401, 403):
                    logger.error("Gemini API authentication failure (401/403). Check GEMINI_API_KEY.")
                    raise LLMError("LLM_CONFIG_ERROR", "Gemini API authentication failed", status_code=status_code)
                elif status_code == 429:
                    if attempt == max_attempts:
                        raise LLMError("LLM_RATE_LIMITED", "Gemini rate limit exceeded after retries", status_code=429)
                    await asyncio.sleep(2 ** attempt)
                elif status_code and status_code >= 500:
                    if attempt == max_attempts:
                        raise LLMError("LLM_UNAVAILABLE", f"Gemini server error: {e}", status_code=status_code)
                    await asyncio.sleep(1.5 ** attempt)
                else:
                    raise LLMError("LLM_UNAVAILABLE", f"Gemini API error: {e}")
            except Exception as e:
                raise LLMError("LLM_UNAVAILABLE", f"Unexpected error communicating with Gemini: {e}")
        else:
            raise LLMError("LLM_UNAVAILABLE", f"Failed to get response after {max_attempts} attempts: {last_error}")

        raw_text = response.text or ""
        
        # Parse JSON
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            # Check if output was truncated
            if "Unterminated" in str(e) or raw_text.rstrip().endswith((",", "{", "[")):
                raise LLMError("LLM_INVALID_OUTPUT", f"Output truncated by token limit: {e}")
            raise LLMError("LLM_INVALID_OUTPUT", f"Invalid JSON returned by LLM: {e}")

        if not isinstance(parsed, list):
            raise LLMError("LLM_INVALID_OUTPUT", "Expected JSON list of findings from LLM")

        findings: list[Finding] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            value = item.get("value")
            evidence = str(item.get("evidence") or "")
            article_type = item.get("articleType")

            if path:
                findings.append(Finding(
                    path=str(path),
                    value=value,
                    evidence=evidence,
                    articleType=str(article_type) if article_type else None,
                ))

        # Token usage
        usage = getattr(response, "usage_metadata", None)
        in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        return LLMExtractResult(
            findings=findings,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            model_name=self.model_name,
            prompt_version=self.prompt_version,
            raw_response=raw_text,
        )
