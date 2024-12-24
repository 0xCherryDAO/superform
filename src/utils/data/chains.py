class Chain:
    def __init__(self, chain_id: int, rpc: str, scan: str, native_token: str) -> None:
        self.chain_id = chain_id
        self.rpc = rpc
        self.scan = scan
        self.native_token = native_token


ETH = Chain(
    chain_id=1,
    rpc='https://rpc.ankr.com/eth',
    scan='https://etherscan.io/tx',
    native_token='ETH',
)

ARB = Chain(
    chain_id=42161,
    rpc='https://arb1.arbitrum.io/rpc',
    scan='https://arbiscan.io/tx',
    native_token='ETH',
)

OP = Chain(
    chain_id=10,
    rpc='https://op-pokt.nodies.app',
    scan='https://optimistic.etherscan.io/tx',
    native_token='ETH',
)

BASE = Chain(
    chain_id=8453,
    rpc='https://base.meowrpc.com',
    scan='https://basescan.org/tx',
    native_token='ETH'
)

chain_mapping = {
    'ETH': ETH,
    'ARB': ARB,
    'OP': OP,
    'BASE': BASE
}
