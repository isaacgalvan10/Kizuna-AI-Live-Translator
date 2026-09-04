# backend/app/database.py
import os
import asyncpg
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Get the URL from docker-compose environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Create the Engine (The Connection Pool)
engine = create_async_engine(
    DATABASE_URL, 
    echo=True
    )

# 3. Create the Session Factory (The Transaction Manager)
AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# 4. Create the Base Model (All tables inherit from this)
Base = declarative_base()

# 5. Dependency Injection (Use this in your Endpoints)
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def connect_with_retry():
    while True:
        try:
            print("⏳ Attempting to connect to database...")
            return await asyncpg.connect(DATABASE_URL)
        except Exception as e:
            print(f"⚠️ Connection failed: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)