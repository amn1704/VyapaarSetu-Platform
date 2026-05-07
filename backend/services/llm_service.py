import json
import logging
import time
import requests
from ollama import Client, ResponseError
from ..config import settings
from .sql_validator import sql_validator
from ..prompts.prompts import (
    TEXT_TO_SQL_SYSTEM_PROMPT,
    TEXT_TO_SQL_SCHEMA_CONTEXT,
    EVIDENCE_SUMMARY_PROMPT,
    ACTIVITY_EXPLAINER_PROMPT,
    REPORT_GENERATOR_PROMPT
)

logger = logging.getLogger("ubid.llm")

import re

# PAN Regex: 5 letters, 4 digits, 1 letter (Standard Indian format)
PAN_REGEX = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")

class LLMService:
    """
    On-premise LLM service using llama3.1:8b via local Ollama.
    Handles SQL generation, summarisation, and reporting.
    """
    
    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model
        self.client = Client(host=settings.OLLAMA_HOST, timeout=120.0)

    def health_check(self) -> dict:
        """Verifies Ollama connectivity and model availability."""
        try:
            # Using requests for direct API check as requested
            url = f"{settings.OLLAMA_HOST}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return {"status": "ok", "models": response.json().get("models", [])}
        except Exception as e:
            raise ConnectionError(f"Ollama service is unreachable at {settings.OLLAMA_HOST}: {e}")

    async def _call_ollama(self, system: str, user: str, temperature: float) -> str:
        """Private helper to manage Ollama chat interactions with retries and logging."""
        
        # CRITICAL SECURITY CHECK: No real PAN may ever be sent to the LLM
        prompt_content = system + " " + user
        if PAN_REGEX.search(prompt_content):
            logger.critical("PII LEAK DETECTED: Attempted to send a real PAN to the LLM!")
            raise ValueError("Security violation: Real PII (PAN) detected in LLM prompt.")

        start_time = time.time()
        try:
            # Wrap in a loop for the single retry requirement
            for attempt in range(2):
                try:
                    response = self.client.chat(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user}
                        ],
                        options={"temperature": temperature}
                    )
                    
                    content = response["message"]["content"].strip()
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    # Log metadata only (no PII/pseudonyms)
                    logger.info(
                        f"LLM Call | Model: {self.model} | Prompt: {len(system)+len(user)} chars | "
                        f"Response: {len(content)} chars | Latency: {latency_ms}ms"
                    )
                    return content
                except ResponseError as re:
                    if attempt == 0:
                        logger.warning(f"Ollama timeout, retrying... {re}")
                        continue
                    raise re
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            raise

    async def text_to_sql(self, user_question: str, schema_context: str | None = None, previous_error: str | None = None, previous_sql: str | None = None) -> str:
        """Generates validated SQL from natural language."""
        repair_context = ""
        if previous_error and previous_sql:
            repair_context = (
                "\n\nThe previous SQL failed. Repair it using the same schema.\n"
                f"Previous SQL:\n{previous_sql}\n"
                f"Error:\n{previous_error}\n"
            )

        schema_aware_question = (
            f"{schema_context or ''}\n\n"
            f"{TEXT_TO_SQL_SCHEMA_CONTEXT}\n\n"
            f"Officer question:\n{user_question}\n\n"
            f"{repair_context}"
            "Return one safe SQLite SELECT query only."
        )
        raw_sql = await self._call_ollama(
            system=TEXT_TO_SQL_SYSTEM_PROMPT,
            user=schema_aware_question,
            temperature=0.0
        )
        
        # Clean fences
        cleaned_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
        
        return sql_validator.sanitise(cleaned_sql)

    async def summarise_evidence(self, evidence_dict: dict) -> str:
        """Generates a concise summary of record linkage evidence."""
        # Note: Caller MUST pseudonymise evidence_dict before passing in
        summary = await self._call_ollama(
            system=EVIDENCE_SUMMARY_PROMPT,
            user=json.dumps(evidence_dict, default=str),
            temperature=0.3
        )
        # Enforce word limit (soft)
        return " ".join(summary.split()[:80])

    async def explain_activity(self, activity_dict: dict) -> str:
        """Explains business lifecycle status based on event history."""
        explanation = await self._call_ollama(
            system=ACTIVITY_EXPLAINER_PROMPT,
            user=json.dumps(activity_dict, default=str),
            temperature=0.2
        )
        return explanation

    async def generate_report(self, query_results: dict) -> str:
        """Generates a formal paragraph summary of query results."""
        report = await self._call_ollama(
            system=REPORT_GENERATOR_PROMPT,
            user=json.dumps(query_results, default=str),
            temperature=0.4
        )
        # Enforce word limit (soft)
        return " ".join(report.split()[:120])

# Global singleton
llm_service = LLMService()
