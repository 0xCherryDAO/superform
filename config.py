MOBILE_PROXY = False
ROTATE_IP = False

SHUFFLE_WALLETS = True

PAUSE_BETWEEN_WALLETS = [20, 50]  # Пауза в секундах [от, до] между кошельками
PAUSE_BETWEEN_MODULES = [20, 50]

DEPOSIT = False  # Депозит в пул
WITHDRAW = False  # Вывод из пулов

REFERRAL_CODES = ['', '']  # Список реферральных кодов


class DepositSettings:
    chain = 'BASE'
    token = 'PIGGY'

    vaults = ['PIGGY BANK']

    amount = 0.001
    use_percentage = True
    deposit_percentage = [1, 1]  # Проценты от 0 до 1. Например, 0.1 - это 10%, 0.17 - 17% и т.д.


class WithdrawSettings:
    chain = 'BASE'
    target_token = 'ETH'  # Токен, в который конвертируется вся ликвидность

    vault_max_limit = 70  # Значение, выше которого не будет выводить. Например, при vault_max_limit = 70 не будет выводить ликвидность, где больше 70$
