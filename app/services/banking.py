
from fastapi import HTTPException
from sqlalchemy import select, update
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

            existing = db.scalar(
                select(Transaction.id).where(
                    Transaction.account_id == account_id,
                    Transaction.reference_id == payload.reference_id,
                )
            )
            if existing is not None:
                raise HTTPException(409, "Duplicate transaction reference_id")

            # Conditional debit prevents the balance from going negative.
            if payload.type == "debit":
                result = db.execute(
                    update(Account)
                    .where(
                        Account.id == account_id,
                        Account.balance >= payload.amount,
                    )
                    .values(balance=Account.balance - payload.amount)
                )
                if result.rowcount != 1:
                    raise HTTPException(400, "Insufficient balance")
            else:
                db.execute(
                    update(Account)
                    .where(Account.id == account_id)
                    .values(balance=Account.balance + payload.amount)
                )

            transaction = Transaction(
                account_id=account_id,
                type=payload.type,
                amount=payload.amount,
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
    amount = payload.amount

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

            # Debit and credit occur within the same database transaction.
            result = db.execute(
                update(Account)
                .where(
                    Account.id == source_id,
                    Account.balance >= amount,
                )
                .values(balance=Account.balance - amount)
            )
            if result.rowcount != 1:
                raise HTTPException(400, "Insufficient balance")

            db.execute(
                update(Account)
                .where(Account.id == destination_id)
                .values(balance=Account.balance + amount)
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

            # Capture the final balances before committing.
            source_balance = db.scalar(
                select(Account.balance).where(Account.id == source_id)
            )
            destination_balance = db.scalar(
                select(Account.balance).where(Account.id == destination_id)
            )

        return {
            "message": "Transfer successful",
            "source_balance": source_balance,
            "destination_balance": destination_balance,
        }

    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Duplicate reference or database constraint violation"
        ) from exc
