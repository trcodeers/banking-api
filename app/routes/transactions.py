
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Transaction
from app.schemas import (
    TransactionCreate,
    TransactionPage,
    TransactionResponse,
    TransferCreate,
    TransferResponse,
)
from app.services.banking import create_transaction, transfer_money

router = APIRouter(tags=["Transactions"])


@router.post(
    "/accounts/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
)
def add_transaction(
    account_id: int,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
):
    return create_transaction(db, account_id, payload)


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=TransactionPage,
)
def list_transactions(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.get(Account, account_id) is None:
        raise HTTPException(404, "Account not found")

    base_query = select(Transaction).where(
        Transaction.account_id == account_id
    )

    total = db.scalar(
        select(func.count()).select_from(base_query.subquery())
    )

    items = db.scalars(
        base_query
        .order_by(Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("/transfers", response_model=TransferResponse)
def transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
):
    return transfer_money(db, payload)
