from asyncio import run, gather, sleep, create_task, set_event_loop_policy
import asyncio
import random
import logging
import sys

from questionary import select, Choice

from src.database.generate_database import generate_database
from src.database.models import engine, init_models
from src.models.route import Route
from src.utils.data.helper import private_keys, proxies
from src.utils.manage_tasks import manage_tasks
from src.utils.retrieve_route import get_routes
from src.utils.runner import *

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

if sys.platform == 'win32':
    set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def get_module():
    result = await select(
        message="Выберете модуль",
        choices=[
            Choice(title="1) Сгенерировать новую базу данных с маршрутами", value=1),
            Choice(title="2) Отработать по базе данных", value=2),
            Choice(title="3) Зарегистрировать реферралов", value=3)
        ],
        qmark="⚙️ ",
        pointer="✅ "
    ).ask_async()
    return result


async def process_task(routes: list[Route]) -> None:
    if not routes:
        logger.success(f'Все задания из базы данных выполнены')
        return

    tasks = []
    for route in routes:
        tasks.append(create_task(process_route(route)))

        time_to_pause = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1]) \
            if isinstance(PAUSE_BETWEEN_WALLETS, list) else PAUSE_BETWEEN_WALLETS
        logger.info(f'Sleeping {time_to_pause} seconds before next wallet...')
        await sleep(time_to_pause)

    await gather(*tasks)


async def process_route(route: Route) -> None:
    if route.wallet.proxy:
        if route.wallet.proxy.proxy_url and MOBILE_PROXY and ROTATE_IP:
            await route.wallet.proxy.change_ip()

    private_key = route.wallet.private_key

    for task in route.tasks:
        if task == 'DEPOSIT':
            completed = await process_superform_deposit(private_key, proxy=route.wallet.proxy)
            if completed:
                await manage_tasks(private_key, task)
        if task == 'WITHDRAW':
            completed = await process_superform_withdraw(private_key, proxy=route.wallet.proxy)
            if completed:
                await manage_tasks(private_key, task)

        time_to_pause = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1]) \
            if isinstance(PAUSE_BETWEEN_MODULES, list) else PAUSE_BETWEEN_MODULES

        logger.info(f'Sleeping {time_to_pause} seconds before next module...')
        await sleep(time_to_pause)


async def main() -> None:
    await init_models(engine)
    module = await get_module()

    if module == 1:
        if SHUFFLE_WALLETS:
            random.shuffle(private_keys)
        logger.debug("Генерация новой базы данных с маршрутами...")
        await generate_database(engine, private_keys)
    elif module == 2:
        logger.debug("Отработка по базе данных...")
        routes = await get_routes(private_keys)
        await process_task(routes)
    elif module == 3:
        logger.debug("Регистрирую реферралов")
        proxy_index = 0
        if SHUFFLE_WALLETS:
            random.shuffle(private_keys)
        for private_key in private_keys:
            proxy = proxies[proxy_index]
            proxy_index = (proxy_index + 1) % len(proxies)
            if proxy:
                change_link = None
                if MOBILE_PROXY:
                    proxy_url, change_link = proxy.split('|')
                else:
                    proxy_url = proxy

                proxy = Proxy(proxy_url=f'http://{proxy_url}', change_link=change_link)
                if change_link and ROTATE_IP and MOBILE_PROXY:
                    await proxy.change_ip()

            await process_register_referral(private_key, proxy)
            time_to_pause = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1]) \
                if isinstance(PAUSE_BETWEEN_WALLETS, list) else PAUSE_BETWEEN_WALLETS
            logger.info(f'Sleeping {time_to_pause} seconds before next wallet...')
            await sleep(time_to_pause)
    else:
        print("Неверный выбор.")
        return


if __name__ == '__main__':
    run(main())
