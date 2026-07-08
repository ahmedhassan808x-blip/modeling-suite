"""
Shared LLM client — provider-agnostic (Anthropic or Google Gemini), same
key-resolution pattern as the rest of the suite, loud failures, injectable
for offline tests.

Provider selection (env `LLM_PROVIDER` overrides; otherwise auto):
  - "anthropic" if ANTHROPIC_API_KEY is available
  - "gemini"    if GEMINI_API_KEY is available (free tier at
                 https://aistudio.google.com/apikey — no card needed)
Auto prefers Anthropic when both keys exist; set LLM_PROVIDER=gemini to
force the free tier.

Both providers support the two call shapes the suite uses:
  ask()             plain completion
  ask_with_search() completion with server-side web search (Anthropic
                    web_search tool / Gemini Google-Search grounding) —
                    what keeps the research layers on TODAY's data.

Every consumer labels its output as AI-generated. Grounding is enforced at
the PROMPT level and at the RENDER level (financial figures are inserted
programmatically from recalculated workbooks, never asked of the model).
"""

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def _anthropic_default():
    return os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")


def _gemini_default():
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class LLMError(RuntimeError):
    pass


def _env_or_dotenv(name: str) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    for env in (Path.cwd() / ".env", REPO_ROOT / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith(name):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def provider() -> str:
    forced = (os.environ.get("LLM_PROVIDER") or "").lower()
    if forced in ("anthropic", "gemini"):
        return forced
    if forced:
        raise LLMError(f"Unknown LLM_PROVIDER={forced!r} "
                       "(use 'anthropic' or 'gemini').")
    if _env_or_dotenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _env_or_dotenv("GEMINI_API_KEY"):
        return "gemini"
    raise LLMError(
        "No LLM key found. Set ANTHROPIC_API_KEY "
        "(console.anthropic.com, paid) or GEMINI_API_KEY "
        "(aistudio.google.com/apikey, free tier) — env var or repo-root "
        ".env; LLM_PROVIDER forces the choice when both exist.")


def llm_available() -> bool:
    try:
        provider()
        return True
    except LLMError:
        return False


def active_model(model: str | None = None) -> str:
    if model:
        return model
    return (_anthropic_default() if provider() == "anthropic"
            else _gemini_default())


# Kept for existing imports/labels; resolved lazily where it matters.
DEFAULT_MODEL = None


def _key(name: str) -> str:
    k = _env_or_dotenv(name)
    if not k:
        raise LLMError(f"No {name} found (env var or repo-root .env).")
    return k


# ---- Anthropic -------------------------------------------------------------

def _anthropic_call(prompt, system, max_tokens, model, tools=None):
    try:
        import anthropic
    except ImportError as e:
        raise LLMError("anthropic package not installed") from e
    try:
        client = anthropic.Anthropic(api_key=_key("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            tools=tools or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content
                       if getattr(b, "type", "") == "text")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Anthropic call failed: {e}") from e


# ---- Gemini ----------------------------------------------------------------

def _gemini_call(prompt, system, max_tokens, model, search=False):
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise LLMError("google-genai package not installed — "
                       "pip3 install google-genai") from e
    try:
        client = genai.Client(api_key=_key("GEMINI_API_KEY"))
        cfg = types.GenerateContentConfig(
            system_instruction=system or None,
            max_output_tokens=max_tokens,
            tools=[types.Tool(google_search=types.GoogleSearch())]
            if search else None)
        resp = client.models.generate_content(model=model, contents=prompt,
                                              config=cfg)
        text = resp.text
        if not text:
            raise LLMError(f"Gemini returned no text "
                           f"(finish info: {resp.candidates})")
        return text
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Gemini call failed: {e}") from e


# ---- public API ------------------------------------------------------------

def ask(prompt: str, system: str = "", max_tokens: int = 2000,
        model: str | None = None) -> str:
    """One-shot text completion via the active provider."""
    p = provider()
    m = active_model(model)
    if p == "anthropic":
        return _anthropic_call(prompt, system, max_tokens, m)
    return _gemini_call(prompt, system, max_tokens, m)


def ask_with_search(prompt: str, system: str = "", max_tokens: int = 4000,
                    model: str | None = None, max_searches: int = 8) -> str:
    """Completion with server-side web search / grounding — for research
    that must reflect TODAY's data, not training priors."""
    p = provider()
    m = active_model(model)
    if p == "anthropic":
        return _anthropic_call(
            prompt, system, max_tokens, m,
            tools=[{"type": "web_search_20250305", "name": "web_search",
                    "max_uses": max_searches}])
    return _gemini_call(prompt, system, max_tokens, m, search=True)


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def _parse_json_object(text: str) -> dict:
    """Parse the first balanced JSON object in the text — tolerates prose
    before/after it, but not truncation or malformed JSON."""
    cleaned = _strip_fences(text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start < 0:
            raise
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        return obj


def ask_json(prompt: str, required_keys=(), system: str = "",
             max_tokens: int = 2500, model: str | None = None,
             llm=None) -> dict:
    """JSON-structured completion with one retry; validates required keys.

    `llm` overrides the completion function (offline tests inject a fake
    with the same (prompt, system, max_tokens) -> str signature).
    """
    call = llm or (lambda p, s, m: ask(p, system=s, max_tokens=m, model=model))
    text = call(prompt, system, max_tokens)
    for attempt in (1, 2):
        try:
            data = _parse_json_object(text)
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
