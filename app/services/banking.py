
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from app.schemas import TransactionCreate, TransferCreate


def create_transaction(
    db: Session,
    account_id: int,
    payload: TransactionCreate,
) -> Transaction:
    try:
        with db.begin():
            account = db.get(Account, account_id)

            if account is None:
                raise HTTPException(404, "Account not found")

            duplicate = db.scalar(
                select(Transaction.id).where(
                    Transaction.account_id == account_id,
                    Transaction.reference_id == payload.reference_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(409, "Duplicate transaction reference_id")

            amount = payload.amount.quantize(Decimal("0.01"))

            if payload.type == "debit":
                if account.balance < amount:
                    raise HTTPException(400, "Insufficient balance")
                account.balance = (account.balance - amount).quantize(
                    Decimal("0.01")
                )
            else:
                account.balance = (account.balance + amount).quantize(
                    Decimal("0.01")
                )

            transaction = Transaction(
                account_id=account_id,
                type=payload.type,
                amount=amount,
                reference_id=payload.reference_id,
            )
            db.add(transaction)
            db.flush()

        db.refresh(transaction)
        return transaction

    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Duplicate reference or database constraint violation"
        ) from exc


def transfer_money(db: Session, payload: TransferCreate) -> dict:
    source_id = payload.source_account_id
    destination_id = payload.destination_account_id
    amount = payload.amount.quantize(Decimal("0.01"))

    try:
        with db.begin():
            source = db.get(Account, source_id)
            destination = db.get(Account, destination_id)

            if source is None:
                raise HTTPException(404, "Source account not found")
            if destination is None:
                raise HTTPException(404, "Destination account not found")

            duplicate = db.scalar(
                select(Transaction.id).where(
                    Transaction.account_id == source_id,
                    Transaction.reference_id == payload.reference_id,
                )
            )
            if duplicate is not None:
                raise HTTPException(409, "Duplicate transfer reference_id")

            if source.balance < amount:
                raise HTTPException(400, "Insufficient balance")

            source.balance = (source.balance - amount).quantize(
                Decimal("0.01")
            )
            destination.balance = (destination.balance + amount).quantize(
                Decimal("0.01")
            )

            db.add_all([
                Transaction(
                    account_id=source_id,
                    type="debit",
                    amount=amount,
                    reference_id=payload.reference_id,
                ),
                Transaction(
                    account_id=destination_id,
                    type="credit",
                    amount=amount,
                    reference_id=payload.reference_id,
                ),
            ])
            db.flush()

            result = {
                "message": "Transfer successful",
                "source_balance": source.balance,
                "destination_balance": destination.balance,
            }

        return result

    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Duplicate reference or database constraint violation"
        ) from exc
