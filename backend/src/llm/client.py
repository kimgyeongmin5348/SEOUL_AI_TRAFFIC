"""Small NVIDIA NIM client isolated from RoadPulse business logic."""

from typing import Any

import httpx

from backend.src.core.config import settings


class LLMError(RuntimeError):
    """Safe, provider-independent LLM failure."""


class NvidiaLLMClient:
    """Call NVIDIA's OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = base_url or settings.nvidia_llm_base_url
        self.model = model or settings.nvidia_llm_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def _endpoint(self) -> str:
        if not self.base_url:
            raise LLMError("LLM 서버 주소가 설정되지 않았습니다.")
        base = self.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    def complete(self, *, system: str, user: str) -> str:
        if not self.configured:
            raise LLMError("NVIDIA LLM 환경변수가 설정되지 않았습니다.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 350,
            "stream": False,
        }
        try:
            response = httpx.post(
                self._endpoint(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMError("LLM이 빈 설명을 반환했습니다.")
            return content.strip()
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("LLM 설명 생성에 실패했습니다.") from exc

