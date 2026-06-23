"""LLM provider runner for trust-cue episode generation."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable, Iterable


class LLMRunnerError(RuntimeError):
    """Raised when a provider call or response parse fails."""


def _balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def extract_json_object(text: str) -> dict:
    """Extract the first JSON object from a raw model response."""
    stripped = text.strip()
    candidates = []
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.I | re.S):
        candidates.append(match.group(1))
    candidates.append(stripped)
    balanced = _balanced_json_object(stripped)
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMRunnerError("could not extract a JSON object from model response")


def parse_episode_response(request: dict, raw_output: str, model: str, provider: str, strict: bool = False) -> dict:
    """Convert a raw provider response into scorer-compatible episode JSON."""
    episode = {
        "packet_id": request["packet_id"],
        "model": model,
        "provider": provider,
        "cue_condition": request.get("cue_condition"),
        "actions": {},
        "self_reported_cues": [],
        "raw_output": raw_output,
    }
    try:
        payload = extract_json_object(raw_output)
        actions = payload.get("actions", {})
        if not isinstance(actions, dict):
            raise LLMRunnerError("response JSON field 'actions' is not an object")
        episode["actions"] = actions
        cues = payload.get("self_reported_cues", [])
        episode["self_reported_cues"] = cues if isinstance(cues, list) else [str(cues)]
    except Exception as exc:
        if strict:
            raise
        episode["parse_error"] = str(exc)
    return episode


def _extract_gene_labels_from_prompt(prompt: str) -> list[str]:
    labels = re.findall(r'"gene_display"\s*:\s*"([^"]+)"', prompt)
    return list(dict.fromkeys(labels))


def mock_defer_response(prompt: str) -> str:
    """Return a valid all-defer episode without calling an API."""
    labels = _extract_gene_labels_from_prompt(prompt)
    actions = {
        label: {
            "action": "defer",
            "confidence": 0.0,
            "rationale": "mock provider used for pipeline validation",
        }
        for label in labels
    }
    return json.dumps({
        "actions": actions,
        "self_reported_cues": ["mock_defer"],
    }, sort_keys=True)


def _openai_response_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)
    return json.dumps(response, sort_keys=True)


def _anthropic_response_text(response: dict) -> str:
    chunks = []
    for content in response.get("content", []):
        if isinstance(content, dict) and content.get("type") == "text" and isinstance(content.get("text"), str):
            chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)
    return json.dumps(response, sort_keys=True)


def openai_responses_call(
    prompt: str,
    model: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 120.0,
    max_output_tokens: int | None = 4096,
    temperature: float | None = None,
) -> str:
    """Call the OpenAI Responses API using only the Python standard library."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMRunnerError("OPENAI_API_KEY is not set")
    endpoint = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": model,
        "input": prompt,
        "store": False,
    }
    if max_output_tokens is not None:
        body["max_output_tokens"] = int(max_output_tokens)
    if temperature is not None:
        body["temperature"] = float(temperature)

    req = urllib.request.Request(
        f"{endpoint}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRunnerError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMRunnerError(f"OpenAI API request failed: {exc}") from exc
    return _openai_response_text(payload)


def anthropic_messages_call(
    prompt: str,
    model: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 120.0,
    max_output_tokens: int | None = 4096,
    temperature: float | None = None,
) -> str:
    """Call Anthropic's Claude Messages API using only the Python standard library."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMRunnerError("ANTHROPIC_API_KEY is not set")
    endpoint = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    body = {
        "model": model,
        "max_tokens": int(max_output_tokens or 4096),
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None:
        body["temperature"] = float(temperature)

    req = urllib.request.Request(
        f"{endpoint}/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRunnerError(f"Anthropic API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMRunnerError(f"Anthropic API request failed: {exc}") from exc
    return _anthropic_response_text(payload)


def _provider_fn(
    provider: str,
    model: str,
    *,
    timeout: float,
    max_output_tokens: int | None,
    temperature: float | None,
) -> Callable[[str], str]:
    if provider == "mock_defer":
        return mock_defer_response
    if provider == "openai_responses":
        return lambda prompt: openai_responses_call(
            prompt,
            model,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    if provider == "anthropic_messages":
        return lambda prompt: anthropic_messages_call(
            prompt,
            model,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    raise ValueError(f"unknown provider {provider!r}")


def iter_llm_episodes(
    requests: Iterable[dict],
    *,
    provider: str,
    model: str,
    limit: int | None = None,
    delay: float = 0.0,
    strict: bool = False,
    continue_on_error: bool = False,
    timeout: float = 120.0,
    max_output_tokens: int | None = 4096,
    temperature: float | None = None,
) -> Iterable[dict]:
    """Yield episode records from request records and an LLM provider."""
    call = _provider_fn(
        provider,
        model,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    for idx, request in enumerate(requests):
        if limit is not None and idx >= limit:
            break
        try:
            raw = call(request["prompt"])
            episode = parse_episode_response(request, raw, model, provider, strict=strict)
        except Exception as exc:
            if not continue_on_error:
                raise
            episode = {
                "packet_id": request["packet_id"],
                "model": model,
                "provider": provider,
                "cue_condition": request.get("cue_condition"),
                "actions": {},
                "self_reported_cues": [],
                "provider_error": str(exc),
            }
        yield episode
        if delay:
            time.sleep(delay)


def run_llm_episodes(
    requests: Iterable[dict],
    *,
    provider: str,
    model: str,
    limit: int | None = None,
    delay: float = 0.0,
    strict: bool = False,
    continue_on_error: bool = False,
    timeout: float = 120.0,
    max_output_tokens: int | None = 4096,
    temperature: float | None = None,
) -> list[dict]:
    """Run request records through a provider and return episode records."""
    return list(iter_llm_episodes(
        requests,
        provider=provider,
        model=model,
        limit=limit,
        delay=delay,
        strict=strict,
        continue_on_error=continue_on_error,
        timeout=timeout,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    ))
