import json
import time

from groq import Groq

from app.config import settings


if not settings.GROQ_API_KEY:

    raise ValueError(
        "GROQ_API_KEY is missing. "
        "Please add it to your .env file."
    )


client = Groq(
    api_key=settings.GROQ_API_KEY
)


# ---------------------------------------------------------
# Default system voice, extracted verbatim so EVERY existing
# caller (script.py, metadata.py, comments.py) keeps its
# exact previous behavior.  New optional parameters below
# default to the previous hardcoded values as well; callers
# that never pass them are byte-for-byte unaffected.
# ---------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are a data visualization "
    "expert and YouTube Shorts "
    "scriptwriter. "
    "Return ONLY valid JSON. "
    "Never return markdown."
)


# ---------------------------------------------------------
# Rate-limit handling.
#
# Groq enforces per-minute token limits that vary by tier
# (the free/low tiers are as tight as 6k-8k TPM).  Script and
# metadata prompts are 3-4k tokens each, so two back-to-back
# LLM calls -- which happen CONSTANTLY in production (script
# generation, then title/metadata, then the engagement
# comment) -- can trip a 429 through no fault of the caller.
#
# Retry policy: on a rate-limit response, wait out the
# remaining token-window and retry (up to MAX_RETRIES).
# Non-rate-limit failures are never retried; they surface
# exactly as before so callers' existing error handling is
# unaffected.
# ---------------------------------------------------------


class GroqLLM:

    MAX_RETRIES = 3

    RETRY_DELAYS_S = (35.0, 70.0, 140.0)

    @staticmethod
    def _is_rate_limit(error: Exception) -> bool:

        text = str(error).lower()

        return (
            "429" in text
            or "rate limit" in text
            or "too many requests" in text
            or "tpm" in text
            or "rpm" in text
        )

    @staticmethod
    def generate_structured(
        prompt: str,
        model: str = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        system: str = DEFAULT_SYSTEM_PROMPT,
    ) -> dict:

        selected_model = (
            model
            or settings.GROQ_MODEL
        )

        last_error = None

        for attempt in range(
            GroqLLM.MAX_RETRIES + 1
        ):

            if attempt > 0:

                delay = GroqLLM.RETRY_DELAYS_S[
                    min(
                        attempt - 1,
                        len(
                            GroqLLM.RETRY_DELAYS_S
                        ) - 1,
                    )
                ]

                print(
                    f"\n⏳ Groq rate limit "
                    f"(429/TPM); retry "
                    f"{attempt}/{GroqLLM.MAX_RETRIES} "
                    f"after {delay:.0f}s..."
                )

                time.sleep(delay)

            try:

                response = client.chat.completions.create(
                    model=selected_model,
                    response_format={
                        "type": "json_object"
                    },
                    messages=[
                        {
                            "role": "system",
                            "content": system
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                content = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                if not content:

                    raise ValueError(
                        "Groq returned empty content."
                    )

                return json.loads(content)

            except json.JSONDecodeError as e:

                raise ValueError(
                    f"Groq returned invalid JSON: {e}"
                )

            except Exception as e:

                last_error = e

                if not GroqLLM._is_rate_limit(e):

                    raise RuntimeError(
                        f"Groq request failed: {e}"
                    )

        raise RuntimeError(
            f"Groq request failed after "
            f"{GroqLLM.MAX_RETRIES} rate-limit "
            f"retries: {last_error}"
        )