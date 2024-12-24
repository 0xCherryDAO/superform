from __future__ import annotations

import random
from typing import Dict, Any, List

from pydantic import BaseModel, model_validator

from src.models.chain import Chain
from src.models.token import Token


class DepositConfig(BaseModel):
    chain: Chain
    token: Token

    vaults: list[str]

    amount: float | list[float]
    use_percentage: bool
    deposit_percentage: float | list[float]

    @model_validator(mode='before')
    @classmethod
    def validate_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        amount = values.get('amount')
        deposit_percentage = values.get('deposit_percentage')

        if isinstance(amount, List):
            if len(amount) != 2 or not all(isinstance(i, (int, float)) for i in amount):
                raise ValueError('amount list must contain exactly two numeric values')
            values['amount'] = round(random.uniform(amount[0], amount[1]), 7)
        elif isinstance(amount, (int, float)):
            values['amount'] = amount

        if isinstance(deposit_percentage, List):
            if len(deposit_percentage) != 2 or not all(isinstance(i, (int, float)) for i in deposit_percentage):
                raise ValueError('deposit_percentage list must contain exactly two numeric values')
            values['deposit_percentage'] = random.uniform(deposit_percentage[0], deposit_percentage[1])
        elif isinstance(deposit_percentage, (int, float)):
            values['deposit_percentage'] = deposit_percentage

        return values


class WithdrawConfig(BaseModel):
    chain: Chain
    target_token: Token


# class SuperFormConfig(BaseModel):
#     deposit_config: DepositConfig = None
#     withdraw_config: WithdrawConfig = None
