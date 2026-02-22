"""
Actian connection pool for async agents.
"""

import asyncpg
import os
from typing import Optional


class ActianPool:
    """Async connection pool for Actian Vector DB"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(
        self,
        host: str = None,
        port: int = 5432,
        user: str = None,
        password: str = None,
        database: str = None,
        min_size: int = 2,
        max_size: int = 10
    ):
        """
        Create connection pool.

        Args from env vars if not provided:
        - ACTIAN_HOST
        - ACTIAN_USER
        - ACTIAN_PASSWORD
        - ACTIAN_DATABASE
        """
        host = host or os.getenv('ACTIAN_HOST', 'localhost')
        user = user or os.getenv('ACTIAN_USER', 'vectordb')
        password = password or os.getenv('ACTIAN_PASSWORD', 'vectordb_pass')
        database = database or os.getenv('ACTIAN_DATABASE', 'safety_rag')

        self.pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=min_size,
            max_size=max_size
        )

        print(f"✅ Actian connection pool created: {host}:{port}/{database}")

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            print("Actian connection pool closed")

    def acquire(self):
        """
        Acquire connection from pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.execute(...)
        """
        if not self.pool:
            raise RuntimeError("Pool not connected. Call connect() first.")
        return self.pool.acquire()

    async def fetch(self, query: str, *args):
        """Execute query and fetch results"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args):
        """Execute query without fetching results"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
