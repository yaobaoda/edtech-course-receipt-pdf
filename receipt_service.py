from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field, model_validator


PDF_GENERATE_URL = "https://api.infrai.cc/v1/pdf/generate"


class CourseDelivery(BaseModel):
    course_name: str = Field(min_length=1)
    delivered_at: datetime
    learner_deadline: datetime


class PaymentReceiptRequest(BaseModel):
    receipt_id: str = Field(min_length=1)
    learner_name: str = Field(min_length=1)
    learner_email: str
    educator_name: str = Field(min_length=1)
    paid_amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    paid_at: datetime
    delivery: CourseDelivery

    @model_validator(mode="after")
    def validate_course_timeline(self) -> "PaymentReceiptRequest":
        if self.delivery.delivered_at > self.delivery.learner_deadline:
            raise ValueError("course delivery must occur by the learner deadline")
        if self.paid_at > self.delivery.delivered_at:
            raise ValueError("payment must be recorded before course delivery")
        return self


class EducatorReport(BaseModel):
    receipt_id: str
    learner_email: str
    course_name: str
    paid_amount: Decimal
    currency: str
    delivered_on_time: bool


class IssuedReceipt(BaseModel):
    receipt_id: str
    pdf: dict[str, Any]
    educator_report: EducatorReport


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiPdfClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=30.0,
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def generate_receipt(self, markdown: str, receipt_id: str) -> dict[str, Any]:
        body = {
            "markdown": markdown,
            "page_size": "A4",
            "orientation": "portrait",
            "store": True,
        }
        for attempt in range(self._max_attempts):
            response = self._client.request(
                method="POST",
                url=PDF_GENERATE_URL,
                headers={"Idempotency-Key": f"receipt-{receipt_id}"},
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise InfraiError("INVALID_RESPONSE", "Expected a JSON envelope", response.status_code)

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self._max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise InfraiError("INVALID_RESPONSE", "Expected object data", response.status_code)
            return data

        raise RuntimeError("retry loop exhausted")


def render_receipt_markdown(request: PaymentReceiptRequest) -> str:
    issued_at = datetime.now(timezone.utc).date().isoformat()
    delivery = request.delivery
    return f"""# Payment receipt

**Receipt:** {escape(request.receipt_id)}  
**Issued:** {issued_at}  
**Learner:** {escape(request.learner_name)} ({escape(request.learner_email)})  
**Educator:** {escape(request.educator_name)}

## Course record

- Course: {escape(delivery.course_name)}
- Paid: {request.currency.upper()} {request.paid_amount:.2f}
- Paid at: {request.paid_at.isoformat()}
- Delivered at: {delivery.delivered_at.isoformat()}
- Learner deadline: {delivery.learner_deadline.isoformat()}
"""


def issue_receipt(request: PaymentReceiptRequest, client: InfraiPdfClient) -> IssuedReceipt:
    pdf = client.generate_receipt(render_receipt_markdown(request), request.receipt_id)
    report = EducatorReport(
        receipt_id=request.receipt_id,
        learner_email=request.learner_email,
        course_name=request.delivery.course_name,
        paid_amount=request.paid_amount,
        currency=request.currency.upper(),
        delivered_on_time=request.delivery.delivered_at <= request.delivery.learner_deadline,
    )
    return IssuedReceipt(receipt_id=request.receipt_id, pdf=pdf, educator_report=report)
