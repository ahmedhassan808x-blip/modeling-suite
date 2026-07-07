"""
Shared Anthropic client — same key-resolution pattern as the rest of the
suite (env var, then .env), loud failures, injectable for offline tests.

Every consumer of this module labels its output as AI-generated analysis.
The grounding rule is enforced at the PROMPT level (use only supplied
material, cite items) and at the RENDER level (financial figures are
inserted programmatically from the recalculated workbooks, never asked of
the model).
"""

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")


class LLMError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    for env in (Path.cwd() / ".env", REPO_ROOT / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("ANTHROPIC_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise LLMError("No ANTHROPIC_API_KEY found (env var or repo-root .env). "
                   "Get one at https://console.anthropic.com")


def ask(prompt: str, system: str = "", max_tokens: int = 2000,
        model: str = DEFAULT_MODEL) -> str:
    """One-shot text completion. Raises LLMError on any failure."""
    try:
        import anthropic
    except ImportError as e:
        raise LLMError("anthropic package not installed — "
                       "pip3 install anthropic") from e
    try:
        client = anthropic.Anthropic(api_key=_key())
        msg = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content if b.type == "text")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Claude call failed: {e}") from e


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def ask_json(prompt: str, required_keys=(), system: str = "",
             max_tokens: int = 2500, model: str = DEFAULT_MODEL,
             llm=None) -> dict:
    """JSON-structured completion with one retry; validates required keys.

    `llm` overrides the completion function (offline tests inject a fake
    with the same (prompt, system, max_tokens) -> str signature).
    """
    call = llm or (lambda p, s, m: ask(p, system=s, max_tokens=m, model=model))
    text = call(prompt, system, max_tokens)
    for attempt in (1, 2):
        try:
            data = json.loads(_strip_fences(text).strip())
            missing = [k for k in required_keys if k not in data]
            if missing:
                raise LLMError(f"LLM JSON missing keys: {missing}")
            return data
        except json.JSONDecodeError:
            if attempt == 2:
                raise LLMError(f"LLM returned invalid JSON twice; last "
                               f"response began: {text[:200]!r}")
            text = call(prompt + "\n\nYour previous response was not valid "
                        "JSON. Return ONLY a valid JSON object, no prose, "
                        "no code fences.", system, max_tokens)
