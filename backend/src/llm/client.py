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

    def complete(self, *, system: str, user: str, max_tokens: int = 800) -> str:
        if not self.configured:
            raise LLMError("NVIDIA LLM 환경변수가 설정되지 않았습니다.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
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
            msg = body["choices"][0]["message"]
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                # If content is empty because reasoning consumed tokens or model put text in reasoning
                reasoning = msg.get("reasoning") or msg.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning.strip():
                    # Check if there is a summary or conclusion
                    return reasoning.strip()[-300:]
                raise LLMError("LLM이 빈 설명을 반환했습니다.")
            return content.strip()
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("LLM 설명 생성에 실패했습니다.") from exc

    def complete_chat(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Send conversation messages and return both thinking process and reply."""
        if not self.configured:
            raise LLMError("NVIDIA LLM 환경변수가 설정되지 않았습니다.")

        chat_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant") and content.strip():
                chat_messages.append({"role": role, "content": content.strip()})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": 0.5,
            "max_tokens": max_tokens,
            "stream": False,
        }
        timeout = timeout_seconds or settings.chat_timeout_seconds or 60.0
        try:
            response = httpx.post(
                self._endpoint(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            msg = choice["message"]
            thinking = msg.get("reasoning") or msg.get("reasoning_content")
            content = msg.get("content") or ""

            # If content is empty but thinking exists and finished due to length, attempt graceful recovery
            if not content.strip() and thinking:
                content = "교통 상황을 분석한 결과입니다. 더 구체적인 구간이나 출발/도착지를 알려주시면 상세히 안내해 드릴게요."

            return {
                "reply": content.strip(),
                "thinking": thinking.strip() if isinstance(thinking, str) and thinking.strip() else None,
                "model": self.model,
            }
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("챗봇 응답 생성에 실패했습니다.") from exc

