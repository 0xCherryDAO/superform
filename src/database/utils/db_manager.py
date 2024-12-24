import types

from typing import (
    Optional,
    Type,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.models import engine, WorkingWallets, WalletsTasks


class DataBaseUtils:
    def __init__(
            self,
            manager_config: DataBaseManagerConfig
    ) -> None:
        self.session = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        self.table_object = manager_config.calculated_table_object

    async def __aenter__(self) -> 'DataBaseUtils':
        return self

    async def __aexit__(self,
                        exc_type: Optional[Type[BaseException]],
                        exc_value: Optional[BaseException],
                        traceback: Optional[types.TracebackType]) -> None:
        await self.session.close()

    async def add_to_db(
            self,
            private_key: str,
            proxy: str = None,
            *,
            status: str,
            task_name: str | None = None
    ) -> None:
        async with self.session() as session:
            query = select(self.table_object).filter_by(private_key=private_key)

            if task_name and self.table_object is WalletsTasks:
                query = query.filter_by(task_name=task_name)

            result = await session.execute(query)
            existing_entry = result.scalars().first()

            if existing_entry:
                existing_entry.status = status
                logger.info(f'🔄 | Updated existing entry '
                            f'with private_key={private_key[:4]}...{private_key[-4:]} and task_name={task_name}')
            else:
                transaction = self.table_object(
                    private_key=private_key,
                    status=status
                )
                if self.table_object is WorkingWallets:
                    transaction.proxy = proxy

                if self.table_object is WalletsTasks:
                    transaction.task_name = task_name

                session.add(transaction)
                logger.success(
                    f'✔️ | Successfully added new entry to DataBase '
                    f'with private_key={private_key[:4]}...{private_key[-4:]} and task_name={task_name}'
                )

            await session.commit()

            if self.table_object is WalletsTasks and status == 'completed':
                await self.check_and_update_working_wallets(private_key, session)

    async def check_and_update_working_wallets(self, private_key: str, session) -> None:
        query = select(WalletsTasks).filter_by(private_key=private_key, status='pending')
        result = await session.execute(query)
        pending_tasks = result.scalars().all()

        if not pending_tasks:
            query = select(WorkingWallets).filter_by(private_key=private_key)
            result = await session.execute(query)
            working_wallet = result.scalars().first()

            if working_wallet:
                working_wallet.status = 'completed'
                await session.commit()
                logger.info(f'✔️ | Updated working_wallets entry to completed for '
                            f'private_key={private_key[:4]}...{private_key[-4:]}')

    async def get_uncompleted_wallets(self):
        async with self.session() as session:
            query = select(WorkingWallets).filter_by(status='pending')
            result = await session.execute(query)
            wallets = result.scalars().all()

        return wallets

    async def get_wallet_pending_tasks(self, private_key: str):
        async with self.session() as session:
            query = select(WalletsTasks).filter_by(private_key=private_key, status='pending')
            result = await session.execute(query)
            tasks = result.scalars().all()

        return tasks
