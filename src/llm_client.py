import json
import os
import time
from typing import Protocol


class RetryExhaustedError(Exception):
    pass


class LLMClient(Protocol):
    def complete(self, system: str, user: str, response_schema: dict) -> dict: ...


class FakeLLMClient:
    """테스트용 스텁. 실제 네트워크 호출 없이 미리 지정된 응답을 순서대로 반환한다."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        self.calls.append({"system": system, "user": user, "schema": response_schema})
        if not self._responses:
            raise RetryExhaustedError("no more queued fake responses")
        return self._responses.pop(0)


class GeminiLLMClient:
    """실제 Gemini API 호출. 구조화된 JSON 출력과 지수 백오프 재시도를 포함한다."""

    def __init__(self, model: str, api_key: str | None = None, max_retries: int = 3):
        from google import genai

        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self._model = model
        self._max_retries = max_retries

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        from google.genai import types

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )
                return json.loads(response.text)
            except Exception as exc:  # noqa: BLE001 - 재시도 대상 예외를 폭넓게 포착
                last_error = exc
                if attempt < self._max_retries - 1:
                    time.sleep(2**attempt)
        raise RetryExhaustedError(f"LLM call failed after {self._max_retries} attempts: {last_error}")


class TimelyLLMClient:
    """Timely 중개 API(OpenAI 호환 REST) 경유로 여러 회사 모델(Claude/Gemini/GPT/Grok)을
    같은 인터페이스로 호출한다. 구조화된 JSON 출력과 재시도를 포함한다."""

    _BASE_URL = "https://hello.timelygpt.co.kr/api/v2/chat/bridge/openai"

    def __init__(self, model: str, api_key: str | None = None, max_retries: int = 3):
        from openai import OpenAI

        self._client = OpenAI(
            base_url=self._BASE_URL,
            api_key=api_key or os.environ["TIMELY_API_KEY"],
        )
        self._model = model
        self._max_retries = max_retries

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "submit_result",
                                "description": "구조화된 태깅 결과를 제출한다.",
                                "parameters": response_schema,
                            },
                        }
                    ],
                    tool_choice={"type": "function", "function": {"name": "submit_result"}},
                )
                tool_call = response.choices[0].message.tool_calls[0]
                return json.loads(tool_call.function.arguments)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                status = getattr(exc, "status_code", None)
                if status == 402:
                    # 크레딧 부족은 재시도해도 소용없으므로 즉시 실패
                    raise RetryExhaustedError(f"Timely 크레딧 부족: {exc}") from exc
                if attempt < self._max_retries - 1:
                    wait = 10 if status == 429 else 2**attempt
                    time.sleep(wait)
        raise RetryExhaustedError(f"Timely 호출 실패 ({self._max_retries}회 시도): {last_error}")
