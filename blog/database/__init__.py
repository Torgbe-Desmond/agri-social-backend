from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()
import os

# Replace this with your actual Supabase password or use an environment variable
DATABASE_URL = "postgresql+asyncpg://postgres.qolhywmalugdwssrxyrl:qHunYTMEUcnSC7i3@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
# ---------------- SYNC (optional, for admin scripts or metadata reflection) ----------------
sync_engine = create_engine(os.getenv("DATABASE_URL").replace("asyncpg", "psycopg2"))  # psycopg2 for sync ops
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Reflect DB schema if needed
metadata = MetaData()
metadata.reflect(bind=sync_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- ASYNC (preferred for FastAPI routes) ----------------
# async_engine = create_async_engine(DATABASE_URL,echo=True,connect_args={"statement_cache_size": 0})  # ✅ CRITICAL for PgBouncer compatibility)

async_engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"statement_cache_size": 0,"timeout": 60},  # 🚀 disables prepared statements
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# ✅ Use this with Depends(get_async_db) in FastAPI routes
async def get_async_db() -> AsyncSession:
    async with async_session() as session:
        yield session
