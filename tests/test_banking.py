
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Account, Transaction
from app.schemas import TransactionCreate
from app.services.banking import create_transaction


from app.schemas import TransferCreate
from app.services.banking import transfer_money


def test_rollback_if_transaction_record_fails(monkeypatch):
    # Use an isolated in-memory database; your banking.db is untouched.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(
        bind=engine, expire_on_commit=False
    )

    try:
        # Arrange: Alice has ₹100.
        with TestSession() as db:
            account = Account(
                name="Alice",
                balance=Decimal("100.00"),
            )
            db.add(account)
            db.commit()
            account_id = account.id

        with TestSession() as db:
            original_flush = db.flush

            # Simulate failure when inserting the transaction record.
            def failing_flush(*args, **kwargs):
                if any(
                    isinstance(obj, Transaction)
                    for obj in db.new
                ):
                    raise RuntimeError("Simulated insert failure")
                return original_flush(*args, **kwargs)

            monkeypatch.setattr(db, "flush", failing_flush)

            with pytest.raises(
                RuntimeError, match="Simulated insert failure"
            ):
                create_transaction(
                    db,
                    account_id,
                    TransactionCreate(
                        type="debit",
                        amount=Decimal("30.00"),
                        reference_id="atomicity-test-001",
                    ),
                )

        # Assert: neither change was persisted.
        with TestSession() as db:
            account = db.get(Account, account_id)
            count = db.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.account_id == account_id
                )
            )

            assert account.balance == Decimal("100.00")
            assert count == 0

        print("PASS: balance and transaction both rolled back")

    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()




def test_transfer_rolls_back_if_transaction_record_fails(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        # Arrange: Alice has ₹100; Bob has ₹50.
        with TestSession() as db:
            alice = Account(name="Alice", balance=Decimal("100.00"))
            bob = Account(name="Bob", balance=Decimal("50.00"))
            db.add_all([alice, bob])
            db.commit()

            alice_id = alice.id
            bob_id = bob.id

        with TestSession() as db:
            original_flush = db.flush

            def failing_flush(*args, **kwargs):
                if any(
                    isinstance(obj, Transaction)
                    for obj in db.new
                ):
                    raise RuntimeError("Simulated transfer record failure")
                return original_flush(*args, **kwargs)

            monkeypatch.setattr(db, "flush", failing_flush)

            with pytest.raises(
                RuntimeError, match="Simulated transfer record failure"
            ):
                transfer_money(
                    db,
                    TransferCreate(
                        source_account_id=alice_id,
                        destination_account_id=bob_id,
                        amount=Decimal("30.00"),
                        reference_id="transfer-atomicity-001",
                    ),
                )

        # Assert: both balances and the ledger remain unchanged.
        with TestSession() as db:
            alice = db.get(Account, alice_id)
            bob = db.get(Account, bob_id)
            transaction_count = db.scalar(
                select(func.count()).select_from(Transaction)
            )

            assert alice.balance == Decimal("100.00")
            assert bob.balance == Decimal("50.00")
            assert transaction_count == 0

        print("PASS: transfer fully rolled back")

    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
