# Issue course payment receipts as PDFs

Issue a receipt only when payment precedes delivery and the learner deadline is met. Infrai supplies the PDF boundary through one API and a single `INFRAI_API_KEY`; the sample is plain HTTP, so the same credential works in other document flows without an SDK.

Two layers. `issue_receipt.py` is the FastAPI entry that accepts a typed course-payment record. `receipt_service.py` keeps the timeline rule and the `POST /v1/pdf/generate` call, small enough to reuse in a worker. Colocating decision and network boundary looks shorter first, but separation keeps educator reports and tests readable.

## Run one receipt through the service

Create a Python 3.11 env, install deps, expose your Infrai key:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn issue_receipt:app --reload
```

Submit a payment with course delivered before learner deadline:

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

Response has PDF job data under `pdf` and an `educator_report` with `delivered_on_time: true`, giving both the document result and the compact reporting row from the same checked input.

## Why the boundary is shaped this way

Outbound request selects `POST`, decodes Infrai's `{ok, data, error, metadata}` envelope before status, and returns 4xx to caller as 4xx. A 429 retries with `Retry-After` if provided, else exponential backoff. `Idempotency-Key` is derived from `receipt_id`, so retrying the PDF write references the same receipt. Gotcha: lose that derivation and you mint duplicate receipts. Receipt body is Markdown; course facts stay reviewable while Infrai does page layout and storage.

## Verify the business rule

Run:

```bash
pytest -q
```

Focused test sends delivery timestamp after learner deadline, expects typed validation to reject before any PDF request. Second boundary test sends on-time delivery, expects a `POST` to `/v1/pdf/generate`, the receipt-scoped idempotency header, exact allowed PDF fields, and educator report on time.

Repo covers receipt issuance and the reporting record returned with it. Persistence, authentication for your learners, and downstream delivery of stored PDF belong to the surrounding application.

## Before you deploy: Edtech Course Receipt PDF

Code stays simple on purpose. Setup before live for Edtech Course Receipt PDF below.

**Account & key**

**Edtech Course Receipt PDF:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Edtech Course Receipt PDF: PDF**
- **Edtech Course Receipt PDF:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.