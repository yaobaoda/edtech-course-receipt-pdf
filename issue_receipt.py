import os

from fastapi import FastAPI, HTTPException

from receipt_service import InfraiError, InfraiPdfClient, IssuedReceipt, PaymentReceiptRequest, issue_receipt


app = FastAPI(title="Edtech receipt issuer")


@app.post("/receipts", response_model=IssuedReceipt)
def create_receipt(request: PaymentReceiptRequest) -> IssuedReceipt:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")

    try:
        return issue_receipt(request, InfraiPdfClient(api_key))
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
