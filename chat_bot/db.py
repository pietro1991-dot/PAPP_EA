import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, Text, JSON, Boolean, func

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://papp_ea:papp_ea_2024@localhost:5432/papp_ea",
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    t: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)  # multi-tenant
    symbol: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    pattern: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dir: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    license_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LicenseKey(Base):
    __tablename__ = "license_keys"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    used_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    # --- campi per l'EA (binding al conto + enforcement abbonamento) ---
    bound_account: Mapped[str | None] = mapped_column(String(40), nullable=True)   # n° conto MT5 a cui è legata
    bound_broker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default="pro")                   # starter|pro|elite
    active: Mapped[bool] = mapped_column(Boolean, default=True)                    # abbonamento attivo
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # scadenza (None=illimitata)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)    # ultimo ping dell'EA
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    t: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), default="EURUSD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    t: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)       # P/L flottante conto
    sym_profit: Mapped[float | None] = mapped_column(Float, nullable=True)   # P/L flottante simbolo
    sym_pct: Mapped[float | None] = mapped_column(Float, nullable=True)      # % su balance
    sym_open: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketFeature(Base):
    """Feature di mercato per barra D1 (dall'export PAPP_Export.csv). Usate per le
    domande di mercato complesse: regime di volatilità/cluster, posizione vs MA, ecc."""
    __tablename__ = "market_features"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    t: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_med: Mapped[float | None] = mapped_column(Float, nullable=True)     # distanza % dalla Median
    d_ma30: Mapped[float | None] = mapped_column(Float, nullable=True)    # distanza % da MA30
    d_ma365: Mapped[float | None] = mapped_column(Float, nullable=True)   # distanza % da MA365
    cluster: Mapped[float | None] = mapped_column(Float, nullable=True)   # cluPct
    velocity: Mapped[float | None] = mapped_column(Float, nullable=True)  # velPct
    accel: Mapped[float | None] = mapped_column(Float, nullable=True)     # accPct
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)  # volPct
    order_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    pattern: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    dir: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pt: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_d: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LlmCache(Base):
    __tablename__ = "llm_cache"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    content: Mapped[str] = mapped_column(Text)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)


# Migrazioni idempotenti: aggiungono le colonne nuove a tabelle già esistenti
# (create_all crea solo le tabelle mancanti, non altera quelle presenti).
_MIGRATIONS = [
    "ALTER TABLE signals ADD COLUMN IF NOT EXISTS user_id INTEGER",
    "ALTER TABLE account_snapshots ADD COLUMN IF NOT EXISTS user_id INTEGER",
    "ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS user_id INTEGER",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS bound_account VARCHAR(40)",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS bound_broker VARCHAR(80)",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'pro'",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP",
    "ALTER TABLE license_keys ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS ix_signals_user_id ON signals (user_id)",
]


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass
