"""
Fake LLM Client for offline testing of Guideline Extraction.
Reference: Guideline Extraction Plan Section 7.3, 10.9 (GE-LLM).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from app.services.guidelines.llm.base import (
    BaseLLMClient,
    Finding,
    LLMExtractResult,
    LLMError,
)


class FakeLLMClient(BaseLLMClient):
    def __init__(
        self,
        canned_findings: list[Finding] | None = None,
        fail_with_code: str | None = None,
        fail_attempts: int = 1,
        malformed_json_attempts: int = 0,
        truncated_json: bool = False,
        delay_seconds: float = 0.0,
        model_name: str = "fake-gemini-2.5",
        prompt_version: str = "v1",
    ):
        self.canned_findings = canned_findings or []
        self.fail_with_code = fail_with_code
        self.fail_attempts = fail_attempts
        self.malformed_json_attempts = malformed_json_attempts
        self.truncated_json = truncated_json
        self.delay_seconds = delay_seconds
        self.model_name = model_name
        self.prompt_version = prompt_version
        
        self.call_count = 0
        self.repair_call_count = 0
        self.recorded_requests: list[dict[str, Any]] = []

    async def extract_findings(
        self,
        chunk_text: str,
        heading_path: str = "",
        repair_context: str | None = None,
    ) -> LLMExtractResult:
        self.call_count += 1
        if repair_context:
            self.repair_call_count += 1

        self.recorded_requests.append({
            "chunk_text": chunk_text,
            "heading_path": heading_path,
            "repair_context": repair_context,
        })

        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        # Check configured failure codes
        if self.fail_with_code and self.call_count <= self.fail_attempts:
            if self.fail_with_code == "TIMEOUT":
                raise LLMError("TIMEOUT", "Provider request timed out", status_code=408)
            elif self.fail_with_code == "LLM_RATE_LIMITED":
                raise LLMError("LLM_RATE_LIMITED", "Provider rate limit exceeded (429)", status_code=429)
            elif self.fail_with_code == "LLM_UNAVAILABLE":
                raise LLMError("LLM_UNAVAILABLE", "Provider service unavailable (503)", status_code=503)
            elif self.fail_with_code == "LLM_CONFIG_ERROR":
                raise LLMError("LLM_CONFIG_ERROR", "Provider authentication error (401)", status_code=401)
            elif self.fail_with_code == "LLM_REFUSED":
                raise LLMError("LLM_REFUSED", "Provider refused to generate content", status_code=400)
            else:
                raise LLMError(self.fail_with_code, f"Provider error: {self.fail_with_code}")

        # Check malformed JSON attempts
        if self.malformed_json_attempts > 0:
            if not repair_context or self.repair_call_count < self.malformed_json_attempts:
                if self.truncated_json:
                    raise LLMError("LLM_INVALID_OUTPUT", "Output cut off by token limit: [{'path': 'general.maxWords', 'val")
                raise LLMError("LLM_INVALID_OUTPUT", "Failed to parse provider response as JSON")

        return LLMExtractResult(
            findings=list(self.canned_findings),
            input_tokens=len(chunk_text) // 4 + 100,
            output_tokens=len(self.canned_findings) * 30 + 50,
            model_name=self.model_name,
            prompt_version=self.prompt_version,
            raw_response=json.dumps([
                {"path": f.path, "value": f.value, "evidence": f.evidence, "articleType": f.articleType}
                for f in self.canned_findings
            ]),
        )

