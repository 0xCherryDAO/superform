from typing import Optional
from datetime import datetime, timezone

from eth_account.messages import encode_defunct
from loguru import logger
import pyuseragents

from config import WithdrawSettings
from src.models.contracts import PoolData, SuperFormData
from src.models.superform import DepositConfig, WithdrawConfig
from src.utils.data.chains import chain_mapping
from src.utils.data.tokens import vault_ids
from src.utils.proxy_manager import Proxy
from src.utils.request_client.client import RequestClient
from src.utils.user.account import Account
from src.utils.wrappers.decorators import retry


class SuperForm(Account, RequestClient):
    def __init__(
            self,
            private_key: str,
            proxy: Proxy | None,
            deposit_config: DepositConfig | None = None,
            withdraw_config: WithdrawConfig | None = None
    ):
        if deposit_config:
            rpc = deposit_config.chain.rpc
        elif withdraw_config:
            rpc = withdraw_config.chain.rpc
        else:
            rpc = None

        Account.__init__(self, private_key=private_key, rpc=rpc, proxy=proxy)
        RequestClient.__init__(self, proxy=proxy)

        self.deposit_config = deposit_config
        self.withdraw_config = withdraw_config

        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://www.superform.xyz',
            'priority': 'u=1, i',
            'referer': 'https://www.superform.xyz/explore/',
            'response-content-type': 'application/json',
            'user-agent': pyuseragents.random(),
        }

    def __str__(self) -> str:
        if self.deposit_config:
            return f'{[{self.wallet_address}]} | Depositing into {self.deposit_config.vaults}'
        elif self.withdraw_config:
            return f'[{self.wallet_address}] | Withdrawing all vaults'
        else:
            return f'[{self.wallet_address}] | Adding referral code'

    async def get_deposit_data(self, amount: float) -> tuple[str, str, int, float]:
        vaults_ids = [vault_ids[vault] for vault in self.deposit_config.vaults]
        single_amount = amount / len(vaults_ids)
        json_data = []
        for vault_id in vaults_ids:
            json_data.append({
                'user_address': self.wallet_address,
                'from_token_address': self.deposit_config.token.address,
                'from_chain_id': await self.web3.eth.chain_id,
                'amount_in': str(single_amount),
                'refund_address': self.wallet_address,
                'vault_id': vault_id,
                'bridge_slippage': 50,
                'swap_slippage': 50,
                'route_type': 'output',
                'exclude_ambs': [],
                'exclude_liquidity_providers': [],
                'exclude_dexes': [],
                'exclude_bridges': [],
            })

        route = await self.make_request(
            method="POST",
            url='https://www.superform.xyz/api/proxy/deposit/calculate/',
            headers=self.headers,
            json=json_data
        )

        response_json = await self.make_request(
            method='POST',
            url='https://www.superform.xyz/api/proxy/deposit/start/',
            headers=self.headers,
            json=route
        )

        to = response_json['to']
        data = response_json['data']
        value = int(response_json['value'])
        value_usd = float(response_json['value_usd'])
        return to, data, value, value_usd

    @retry(retries=3, delay=30, backoff=1.5)
    async def deposit(self) -> Optional[bool]:
        native_balance = await self.get_wallet_balance(is_native=True)
        if native_balance == 0:
            logger.error(f'[{self.wallet_address}] | ETH balance is 0')
            return

        amount = self.deposit_config.amount
        if self.deposit_config.use_percentage:
            if self.deposit_config.token.name.upper() == 'ETH':
                amount = native_balance / 10 ** 18 * self.deposit_config.deposit_percentage
            else:
                deposit_token_balance = await self.get_wallet_balance(
                    is_native=False,
                    address=self.deposit_config.token.address
                )
                if deposit_token_balance == 0:
                    logger.error(f'[{self.wallet_address}] | {self.deposit_config.token.name} balance is 0')
                    return

                decimals = await self.get_decimals(self.deposit_config.token.address, self.web3)
                amount = deposit_token_balance / 10 ** decimals

        to, data, value, value_usd = await self.get_deposit_data(amount)
        if self.deposit_config.token.name != 'ETH':
            await self.approve_token(
                amount=amount,
                private_key=self.private_key,
                from_token_address=self.deposit_config.token.address,
                spender=to,
                address_wallet=self.wallet_address,
                web3=self.web3
            )

        tx = {
            'chainId': await self.web3.eth.chain_id,
            'from': self.wallet_address,
            'to': self.web3.to_checksum_address(to),
            'nonce': await self.web3.eth.get_transaction_count(self.wallet_address),
            'value': value,
            'gasPrice': int(await self.web3.eth.gas_price * 1.2),
            'data': data
        }
        gas = await self.web3.eth.estimate_gas(tx)
        tx['gas'] = gas
        tx_hash = await self.sign_transaction(tx)
        confirmed = await self.wait_until_tx_finished(tx_hash)
        if confirmed:
            logger.success(
                f'Successfully deposited {self.deposit_config.token.name} | '
                f'TX: {chain_mapping[self.deposit_config.chain.chain_name.upper()].scan}/{tx_hash}'
            )
            return True

    async def get_deposits(self):
        params = {
            'fetch_erc20s': 'true',
        }
        response_json = await self.make_request(
            url=f'https://www.superform.xyz/api/proxy/token/superpositions/balances/{self.wallet_address}/',
            params=params,
        )
        return response_json

    async def get_withdraw_data(self, deposits):
        superpositions = deposits['superpositions']
        if not superpositions:
            logger.warning(f'[{self.wallet_address}] | Positions not found')
            return None, "Empty", None
        superposition_ids = [superposition['superposition_id'] for superposition in superpositions
                             if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]
        vaults_ids = [superposition['vault']['id'] for superposition in superpositions
                      if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]
        balances = [superposition['superposition_balance'] for superposition in superpositions
                    if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]
        chain_ids = [superposition['chain_id'] for superposition in superpositions
                     if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]

        json_data = []
        for superposition_id, vault_id, balance, chain_id in zip(superposition_ids, vaults_ids, balances, chain_ids):
            json_data.append({
                'bridge_slippage': 50,
                'exclude_ambs': [],
                'exclude_bridges': [],
                'exclude_dexes': [],
                'exclude_liquidity_providers': [],
                'is_erc20': False,
                'refund_address': self.wallet_address,
                'retain_4626': False,
                'route_type': 'output',
                'superform_id': superposition_id,
                'superpositions_amount_in': str(balance),
                'superpositions_chain_id': chain_id,
                'swap_slippage': 50,
                'to_chain_id': self.withdraw_config.chain.chain_id,
                'to_token_address': self.withdraw_config.target_token.address,
                'user_address': self.wallet_address,
                'vault_id': vault_id,
            })

        route = await self.make_request(
            method='POST',
            url='https://www.superform.xyz/api/proxy/withdraw/calculate/',
            headers=self.headers,
            json=json_data
        )

        response_json = await self.make_request(
            method='POST',
            url='https://www.superform.xyz/api/proxy/withdraw/start/',
            headers=self.headers,
            json=route
        )
        to = response_json['to']
        data = response_json['data']
        value = int(response_json['value'])
        return to, data, value

    @retry(retries=3, delay=30, backoff=1.5)
    async def withdraw(self) -> Optional[bool]:
        deposits = await self.get_deposits()
        approved = await self.set_approval(deposits)

        if not approved:
            logger.error(f'[{self.wallet_address}] | Approve failed')
            return

        to, data, value = await self.get_withdraw_data(deposits)
        if data == "Empty":
            return True
        tx = {
            'chainId': await self.web3.eth.chain_id,
            'from': self.wallet_address,
            'to': self.web3.to_checksum_address(to),
            'nonce': await self.web3.eth.get_transaction_count(self.wallet_address),
            'value': value,
            'gasPrice': int(await self.web3.eth.gas_price * 1.2),
            'data': data
        }
        gas = await self.web3.eth.estimate_gas(tx)
        tx['gas'] = gas
        tx_hash = await self.sign_transaction(tx)
        confirmed = await self.wait_until_tx_finished(tx_hash)
        if confirmed:
            logger.success(
                f'Successfully withdrawn all vaults | '
                f'TX: {chain_mapping[self.withdraw_config.chain.chain_name.upper()].scan}/{tx_hash}'
            )
            return True

    async def set_approval(self, deposits) -> Optional[bool]:
        approval_contract = self.load_contract(
            address=PoolData.address,
            web3=self.web3,
            abi=PoolData.abi
        )
        superpositions = deposits['superpositions']
        superposition_ids = [int(superposition['superposition_id']) for superposition in superpositions
                             if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]
        balances = [int(superposition['superposition_balance']) for superposition in superpositions
                    if float(superposition['superposition_usd_value']) < WithdrawSettings.vault_max_limit]

        tx = await approval_contract.functions.setApprovalForMany(
            self.web3.to_checksum_address(SuperFormData.address),
            superposition_ids,
            balances
        ).build_transaction({
            'value': 0,
            'nonce': await self.web3.eth.get_transaction_count(self.wallet_address),
            'from': self.wallet_address,
            'gasPrice': int(await self.web3.eth.gas_price * 1.2)
        })
        tx_hash = await self.sign_transaction(tx)
        completed = await self.wait_until_tx_finished(tx_hash)
        if completed:
            logger.success(
                f'Successfully approved spend | '
                f'TX: {chain_mapping[self.withdraw_config.chain.chain_name].scan}/{tx_hash}'
            )
            return True

    async def get_nonce(self) -> str:
        response_json = await self.make_request(
            url=f'https://app.dynamicauth.com/api/v0/sdk/fb9f65d6-a8c4-4f59-8be3-c5a34a01caa5/nonce',
            headers=self.headers
        )
        nonce = response_json['nonce']
        return nonce

    def get_signature(self, nonce: str, formatted_time: str, referral_code: str) -> tuple[str, str]:
        text = f"www.superform.xyz wants you to sign in with your Ethereum account:\n{self.wallet_address}\n\nLog into Superform\n\nURI: https://www.superform.xyz/explore/?ref={referral_code}\nVersion: 1\nChain ID: 8453\nNonce: {nonce}\nIssued At: {formatted_time}\nRequest ID: fb9f65d6-a8c4-4f59-8be3-c5a34a01caa5"

        signed_message = self.web3.eth.account.sign_message(
            encode_defunct(text=text), private_key=self.private_key
        )
        signature = signed_message.signature.hex()
        return '0x' + signature, text

    async def get_auth_token(self, signature: str, msg: str):
        json_data = {
            'signedMessage': signature,
            'messageToSign': msg,
            'publicWalletAddress': self.wallet_address,
            'chain': 'EVM',
            'walletName': 'rabby',
            'walletProvider': 'browserExtension',
            'network': '8453',
            'additionalWalletAddresses': [],
        }
        response_json = await self.make_request(
            method="POST",
            url='https://app.dynamicauth.com/api/v0/sdk/fb9f65d6-a8c4-4f59-8be3-c5a34a01caa5/verify',
            headers=self.headers,
            json=json_data,
        )
        jwt = response_json['jwt']
        if jwt:
            logger.success(f'[{self.wallet_address}] | Successfully grabbed auth token')
            self.headers.update({'sf-jwt': jwt})
            return True
        return False

    @retry(retries=3, delay=30, backoff=1.5)
    async def register_referral(self, referral_code: str):
        nonce = await self.get_nonce()
        current_time = datetime.now(timezone.utc)
        formatted_time = current_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        signature, msg = self.get_signature(nonce, formatted_time, referral_code)
        auth_token = await self.get_auth_token(signature, msg)
        if not auth_token:
            logger.error(f'[{self.wallet_address}] | Failed to get auth token.')
            return

        response_json = await self.make_request(
            url=f'https://www.superform.xyz/api/proxy/superrewards/referrals/redeem/{referral_code}/',
            headers=self.headers
        )
        if response_json['success']:
            logger.success(f'[{self.wallet_address}] | Successfully added referral')
            return True
