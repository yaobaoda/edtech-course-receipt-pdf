from unittest.mock import ANY

import httpx
import pytest
from pydantic import ValidationError

from receipt_service import InfraiPdfClient, PaymentReceiptRequest, issue_receipt


def receipt_input(*, delivered_at: str = "2026-09-08T09:00:00+00:00") -> dict:
    return {
        "receipt_id": "rcpt-course-1042",
        "learner_name": "Ari Chen",
        "learner_email": "ari@example.edu",
        "educator_name": "Northwind Learning",
        "paid_amount": "149.00",
        "currency": "usd",
        "paid_at": "2026-09-07T09:00:00+00:00",
        "delivery": {
            "course_name": "Practical RAG Evaluation",
            "delivered_at": delivered_at,
            "learner_deadline": "2026-09-10T23:59:00+00:00",
        },
    }


def test_late_course_delivery_prevents_receipt_issue() -> None:
    with pytest.raises(ValidationError, match="course delivery must occur"):
        PaymentReceiptRequest.model_validate(
            receipt_input(delivered_at="2026-09-11T00:00:00+00:00")
        )


def test_issued_receipt_carries_report_and_exact_pdf_boundary() -> None:
    seen: dict = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["authorization"] = request.headers["Authorization"]
        seen["idempotency"] = request.headers["Idempotency-Key"]
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {"job_id": "job_1042", "status": "queued"},
                "error": None,
                "metadata": {"request_id": "req_1042"},
            },
        )

    client = InfraiPdfClient("test-key", transport=httpx.MockTransport(handle))
    result = issue_receipt(PaymentReceiptRequest.model_validate(receipt_input()), client)

    assert result.educator_report.delivered_on_time is True
    assert result.educator_report.course_name == "Practical RAG Evaluation"
    assert result.pdf["job_id"] == "job_1042"
    assert seen == {
        "method": "POST",
        "path": "/v1/pdf/generate",
        "authorization": "Bearer test-key",
        "idempotency": "receipt-rcpt-course-1042",
        "body": {
            "markdown": ANY,
            "page_size": "A4",
            "orientation": "portrait",
            "store": True,
        },
    }
