from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from environs import Env

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_BOT_HOST = "0.0.0.0"
DEFAULT_BOT_PORT = 8090

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    TOKEN: str
    ADMINS: list[int]
    DEV_ID: int
    DOMAIN: str
    PORT: int
    USE_POLLING: bool


@dataclass
class XUIConfig:
    HOST: str        # https://p.nexoranode.xyz:2087
    PATH: str        # /CC6AiFGmYY4ZWVRf08
    USERNAME: str
    PASSWORD: str
    TOKEN: str | None
    SUB_BASE_URL: str  # https://s.nexoranode.xyz:2096/s/
    WS_INBOUND_NAME: str    # NX-WS
    REALITY_INBOUND_NAME: str  # NX-Reality

    @property
    def base_url(self) -> str:
        return self.HOST.rstrip("/") + "/" + self.PATH.strip("/")


@dataclass
class DatabaseConfig:
    URL: str  # full asyncpg DSN


@dataclass
class RedisConfig:
    HOST: str
    PORT: int
    DB: str
    USERNAME: str | None
    PASSWORD: str | None

    def url(self) -> str:
        if self.USERNAME and self.PASSWORD:
            return f"redis://{self.USERNAME}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB}"
        return f"redis://{self.HOST}:{self.PORT}/{self.DB}"


@dataclass
class PaymentConfig:
    CARD_NUMBER: str
    CARD_OWNER: str
    ADMIN_CHAT_ID: int
    AGENCY_ADMIN_CHAT_ID: int
    SUPPORT_USERNAME: str


@dataclass
class PricingConfig:
    # Regular plans: price in Toman, traffic in GB, duration in days
    PLANS: dict = field(default_factory=dict)
    BULK_PLANS: dict = field(default_factory=dict)
    # Referral
    REFERRAL_BONUS_MB: int = 500
    REFERRAL_FRIEND_BONUS_MB: int = 200
    # Free trial
    FREE_TRIAL_MB: int = 100
    FREE_TRIAL_DAYS: int = 1


@dataclass
class LoggingConfig:
    LEVEL: str
    FORMAT: str


@dataclass
class Config:
    bot: BotConfig
    xui: XUIConfig
    database: DatabaseConfig
    redis: RedisConfig
    payment: PaymentConfig
    pricing: PricingConfig
    logging: LoggingConfig


def load_config() -> Config:
    env = Env()
    env.read_env()

    admins = env.list("BOT_ADMINS", subcast=int, default=[])
    if not admins:
        logger.warning("BOT_ADMINS is empty.")

    xui_token = env.str("XUI_TOKEN", default=None)

    plans = {
        "bronze": {
            "name": "پلن برنزی",
            "emoji": "🥉",
            "duration_days": 30,
            "traffic_gb": 10,
            "price": env.int("PRICE_BRONZE", default=170000),
        },
        "silver": {
            "name": "پلن نقره‌ای",
            "emoji": "🥈",
            "duration_days": 30,
            "traffic_gb": 30,
            "price": env.int("PRICE_SILVER", default=450000),
        },
        "gold": {
            "name": "پلن طلایی",
            "emoji": "🥇",
            "duration_days": 30,
            "traffic_gb": 50,
            "price": env.int("PRICE_GOLD", default=650000),
        },
        "diamond": {
            "name": "پلن الماس",
            "emoji": "💎",
            "duration_days": 30,
            "traffic_gb": 100,
            "price": env.int("PRICE_DIAMOND", default=1100000),
        },
    }

    bulk_plans = {
        "bulk_10g": {
            "name": "بسته ۱۰ گیگ",
            "traffic_gb": 10,
            "price": env.int("PRICE_BULK_10GB", default=170000),
        },
        "bulk_30g": {
            "name": "بسته ۳۰ گیگ",
            "traffic_gb": 30,
            "price": env.int("PRICE_BULK_30GB", default=450000),
        },
        "bulk_50g": {
            "name": "بسته ۵۰ گیگ",
            "traffic_gb": 50,
            "price": env.int("PRICE_BULK_50GB", default=650000),
        },
        "bulk_100g": {
            "name": "بسته ۱۰۰ گیگ",
            "traffic_gb": 100,
            "price": env.int("PRICE_BULK_100GB", default=1100000),
        },
    }

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            ADMINS=admins,
            DEV_ID=env.int("BOT_DEV_ID", default=0),
            DOMAIN=f"https://{env.str('BOT_DOMAIN', default='localhost')}",
            PORT=env.int("BOT_PORT", default=DEFAULT_BOT_PORT),
            USE_POLLING=env.bool("BOT_USE_POLLING", default=False),
        ),
        xui=XUIConfig(
            HOST=env.str("XUI_HOST", default="https://p.nexoranode.xyz:2087"),
            PATH=env.str("XUI_PATH", default="/CC6AiFGmYY4ZWVRf08"),
            USERNAME=env.str("XUI_USERNAME"),
            PASSWORD=env.str("XUI_PASSWORD"),
            TOKEN=xui_token,
            SUB_BASE_URL=env.str("XUI_SUB_BASE_URL", default="https://s.nexoranode.xyz:2096/s/"),
            WS_INBOUND_NAME=env.str("XUI_WS_INBOUND_NAME", default="NX-WS"),
            REALITY_INBOUND_NAME=env.str("XUI_REALITY_INBOUND_NAME", default="NX-Reality"),
        ),
        database=DatabaseConfig(
            URL=env.str(
                "DATABASE_URL",
                default="sqlite+aiosqlite:////" + str(DEFAULT_DATA_DIR / "nexorabot.sqlite3"),
            ),
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST", default="3xui-shop-redis"),
            PORT=env.int("REDIS_PORT", default=6379),
            DB=env.str("REDIS_DB_NAME", default="0"),
            USERNAME=env.str("REDIS_USERNAME", default=None),
            PASSWORD=env.str("REDIS_PASSWORD", default=None),
        ),
        payment=PaymentConfig(
            CARD_NUMBER=env.str("CARD_NUMBER", default="6037-XXXX-XXXX-XXXX"),
            CARD_OWNER=env.str("CARD_OWNER", default="نکسورانود"),
            ADMIN_CHAT_ID=env.int("ADMIN_CHAT_ID", default=0),
            AGENCY_ADMIN_CHAT_ID=env.int("AGENCY_ADMIN_CHAT_ID", default=0),
            SUPPORT_USERNAME=env.str("SUPPORT_USERNAME", default="@nexorasupport"),
        ),
        pricing=PricingConfig(
            PLANS=plans,
            BULK_PLANS=bulk_plans,
            REFERRAL_BONUS_MB=env.int("REFERRAL_BONUS_MB", default=500),
            REFERRAL_FRIEND_BONUS_MB=env.int("REFERRAL_FRIEND_BONUS_MB", default=200),
            FREE_TRIAL_MB=env.int("FREE_TRIAL_MB", default=100),
            FREE_TRIAL_DAYS=env.int("FREE_TRIAL_DAYS", default=1),
        ),
        logging=LoggingConfig(
            LEVEL=env.str("LOG_LEVEL", default="DEBUG"),
            FORMAT=env.str(
                "LOG_FORMAT",
                default="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            ),
        ),
    )
