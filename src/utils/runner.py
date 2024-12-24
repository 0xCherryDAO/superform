import random
from typing import Optional

from loguru import logger

from src.models.chain import Chain
from src.models.superform import DepositConfig, WithdrawConfig
from src.models.token import Token
from src.superform.superform import SuperForm
from src.utils.proxy_manager import Proxy
from src.utils.data.chains import chain_mapping
from config import *


async def process_superform_deposit(private_key: str, proxy: Proxy | None) -> Optional[bool]:
    deposit_settings = DepositConfig(
        chain=Chain(
            chain_name=DepositSettings.chain,
            native_token=chain_mapping[DepositSettings.chain.upper()].native_token,
            rpc=chain_mapping[DepositSettings.chain.upper()].rpc,
            chain_id=chain_mapping[DepositSettings.chain.upper()].chain_id
        ),
        token=Token(
            chain_name=DepositSettings.chain,
            name=DepositSettings.token,
        ),
        vaults=DepositSettings.vaults,
        amount=DepositSettings.amount,
        use_percentage=DepositSettings.use_percentage,
        deposit_percentage=DepositSettings.deposit_percentage,
    )

    superform = SuperForm(
        private_key=private_key,
        proxy=proxy,
        deposit_config=deposit_settings,
        withdraw_config=None
    )
    logger.debug(superform)
    deposited = await superform.deposit()
    if deposited:
        return True


async def process_superform_withdraw(private_key: str, proxy: Proxy | None) -> Optional[bool]:
    superform = SuperForm(
        private_key=private_key,
        proxy=proxy,
        deposit_config=None,
        withdraw_config=WithdrawConfig(
            chain=Chain(
                chain_name=WithdrawSettings.chain,
                native_token=chain_mapping[DepositSettings.chain.upper()].native_token,
                rpc=chain_mapping[DepositSettings.chain.upper()].rpc,
                chain_id=chain_mapping[DepositSettings.chain.upper()].chain_id
            ),
            target_token=Token(
                chain_name=WithdrawSettings.chain,
                name=WithdrawSettings.target_token
            )
        )
    )
    logger.debug(superform)
    withdrawn = await superform.withdraw()
    if withdrawn:
        return True


async def process_register_referral(private_key: str, proxy: Proxy | None):
    superform = SuperForm(
        private_key=private_key,
        proxy=proxy,
    )
    logger.debug(superform)
    referral_code = random.choice(REFERRAL_CODES)
    await superform.register_referral(referral_code)
