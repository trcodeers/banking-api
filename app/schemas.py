
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Account name must not be empty")
        return value


class AccountResponse(BaseModel):
    id: int
    name: str
    balance: int  # Balance in paise

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    type: Literal["credit", "debit"]
    amount: int = Field(gt=0, description="Amount in paise")
    reference_id: str = Field(min_length=1, max_length=100)

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reference_id must not be empty")
        return value


class TransactionResponse(BaseModel):
    id: int
    account_id: int
    type: Literal["credit", "debit"]
    amount: int
    reference_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionPage(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int


class TransferCreate(BaseModel):
    source_account_id: int = Field(gt=0)
    destination_account_id: int = Field(gt=0)
    amount: int = Field(gt=0, description="Amount in paise")
    reference_id: str = Field(min_length=1, max_length=100)

    @field_validator("reference_id")
    @classmethod
    def validate_reference_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reference_id must not be empty")
        return value

    @field_validator("destination_account_id")
    @classmethod
    def validate_different_accounts(
        cls, value: int, info
    ) -> int:
        source_id = info.data.get("source_account_id")
        if source_id == value:
            raise ValueError("Source and destination accounts must differ")
        return value


class TransferResponse(BaseModel):
    message: str
    source_balance: int
    destination_balance: int
