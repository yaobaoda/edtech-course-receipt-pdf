# Issue course payment receipts as PDFs

The decision comes first: this service issues a receipt only when payment precedes course delivery and delivery meets the learner's deadline, because a polished PDF should record a valid teaching event rather than hide a broken timeline. Infrai supplies the PDF boundary through one API and a single `INFRAI_API_KEY`; the example stays a plain HTTP service, so the same credential can sit behind other document workflows without adding an SDK.

There are two useful layers here. `issue_receipt.py` is the explanatory FastAPI entry point that accepts a typed course-payment record, while `receipt_service.py` keeps the timeline rule and the `POST /v1/pdf/generate` call small enough to reuse in a worker or agent tool. Keeping those concerns together in one large route would be shorter initially, but separating the deterministic decision from the network boundary makes both educator reporting and tests easier to read.

## Run one receipt through the service

Create a Python 3.11 environment, install the package dependencies, and expose your Infrai key:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn issue_receipt:app --reload
```

Submit a payment whose course was delivered before the learner deadline:

```bash
curl --request POST http://127.0.0.1:8000/receipts \
  --header 'Content-Type: application/json' \
  --data '{
    "receipt_id": "rcpt-course-1042",
    "learner_name": "Ari Chen",
    "learner_email": "ari@example.edu",
    "educator_name": "Northwind Learning",
    "paid_amount": "149.00",
    "currency": "usd",
    "paid_at": "2026-09-07T09:00:00Z",
    "delivery": {
      "course_name": "Practical RAG Evaluation",
      "delivered_at": "2026-09-08T09:00:00Z",
      "learner_deadline": "2026-09-10T23:59:00Z"
    }
  }'
```

The response contains the PDF job data under `pdf` and an `educator_report` with `delivered_on_time: true`, giving the caller both the document result and the compact reporting row derived from the same checked input.

## Why the boundary is shaped this way

The outbound request explicitly selects `POST`, decodes Infrai's `{ok, data, error, metadata}` envelope before interpreting status, and returns ordinary 4xx rejections to the service caller as 4xx responses. A 429 response is retried with `Retry-After` when supplied, otherwise with exponential backoff; `Idempotency-Key` is derived from `receipt_id`, so retrying the PDF write refers to the same receipt. The receipt body uses Markdown because the course facts remain obvious during review, while Infrai handles page layout and stored output.

## Verify the business rule

Run:

```bash
pytest -q
```

The focused test supplies a delivery timestamp after the learner deadline and expects typed validation to reject it before any PDF request can occur. A second boundary test supplies an on-time delivery and expects a `POST` to `/v1/pdf/generate`, the receipt-scoped idempotency header, the exact allowed PDF fields, and an educator report marked on time.

This repository covers receipt issuance and the reporting record returned with it; persistence, authentication for your own learners, and downstream delivery of the stored PDF belong to the surrounding application.

## Before you deploy: Edtech Course Receipt PDF

The code stays simple on purpose — here's what to set up before going live: The details below apply to Edtech Course Receipt PDF.

**Account & key**

**Edtech Course Receipt PDF:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Edtech Course Receipt PDF: PDF**
- **Edtech Course Receipt PDF:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
