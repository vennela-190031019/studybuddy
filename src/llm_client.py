"""
Small wrapper around the LLM API call. Keeping this isolated means if you
ever want to swap providers (e.g. to Anthropic's Claude API), you only
change this one file — nothing else in the app needs to know or care.
"""
import json
import os
from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and "
                "add your key, or set it as an environment variable."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def call_llm_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """
    Calls the model and asks it to return JSON only. Returns a parsed dict.
    Raises ValueError if the model didn't return valid JSON (rare, but LLMs
    aren't perfect — this is where you'd add a retry loop in a v2).
    """
    client = get_client()
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON:\n{raw}") from e
