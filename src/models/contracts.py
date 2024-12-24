from dataclasses import dataclass


@dataclass
class ERC20:
    abi: str = open('./assets/abi/erc20.json', 'r').read()


@dataclass
class SuperFormData:
    address: str = '0xa195608C2306A26f727d5199D5A382a4508308DA'
    abi: str = open('./assets/abi/superform.json', 'r').read()


@dataclass
class PoolData:
    address: str = '0x01dF6fb6a28a89d6bFa53b2b3F20644AbF417678'
    abi: str = open('./assets/abi/pool.json', 'r').read()
