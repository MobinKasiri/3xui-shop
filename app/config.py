from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from environs import Env

from app.bot.services.required_channels import RequiredChannel, parse_required_channels

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_PLANS_FILE = DEFAULT_DATA_DIR / "plans.json"
DEFAULT_BOT_HOST = "0.0.0.0"
DEFAULT_BOT_PORT = 8090

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    TOKEN: str
    USERNAME: str
    ADMINS: list[int]
    DEV_ID: int
    DOMAIN: str
    PORT: int
    USE_POLLING: bool
    REQUIRED_CHANNELS: tuple[RequiredChannel, ...] = ()


@dataclass
class XUIConfig:
    HOST: str
    PATH: str
    USERNAME: str
    PASSWORD: str
    TOKEN: str | None
    SUB_BASE_URL: str
    INBOUND_FILTER: tuple[str, ...] = ()
    START_AFTER_FIRST_USE: bool = True
    DEFAULT_DURATION_DAYS: int = 30
    NODE_SYNC_ENABLED: bool = True
    NODE_SSH_USER: str = "root"
    NODE_SSH_PORT: int = 22

    @property
    def base_url(self) -> str:
        return self.HOST.rstrip("/") + "/" + self.PATH.strip("/")


@dataclass
class DatabaseConfig:
    URL: str


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
    CARD_BANK: str
    ADMIN_CHAT_ID: int
    SUPPORT_USERNAME: str  # without leading @


@dataclass
class PricingConfig:
    """All plans, keyed by tier id ('vip', 'regular'). Each tier has plans list."""

    TIERS: dict = field(default_factory=dict)
    REFERRAL_BONUS_TOMAN: int = 50000
    REFERRAL_FRIEND_BONUS_TOMAN: int = 5000
    QUANTITY_MAX: int = 20
    plans_file: Path | None = field(default=None, repr=False)
    _plans_mtime: float = field(default=0.0, init=False, repr=False)

    def reload_plans_if_changed(self) -> None:
        """Reload plans.json when the file changes (e.g. after panel save)."""
        if not self.plans_file or not self.plans_file.is_file():
            return
        try:
            mtime = self.plans_file.stat().st_mtime
            if mtime == self._plans_mtime:
                return
            with self.plans_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self.TIERS = data
                self._plans_mtime = mtime
                logger.info("Reloaded plans from %s (%d tiers)", self.plans_file, len(self.TIERS))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not reload plans from %s: %s", self.plans_file, exc)

    def get_plan(self, plan_id: str) -> dict | None:
        self.reload_plans_if_changed()
        for tier in self.TIERS.values():
            for plan in tier.get("plans", []):
                if plan.get("id") == plan_id:
                    return {**plan, "tier_name": tier.get("name", "")}
        return None

    def list_plans(self, tier_id: str) -> list[dict]:
        self.reload_plans_if_changed()
        tier = self.TIERS.get(tier_id, {})
        return tier.get("plans", [])

    def tier_name(self, tier_id: str) -> str:
        self.reload_plans_if_changed()
        return self.TIERS.get(tier_id, {}).get("name", "")


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


def _normalize_bot_domain(raw: str) -> str:
    domain = raw.strip().rstrip("/")
    if domain.startswith("https://"):
        domain = domain[len("https://"):]
    elif domain.startswith("http://"):
        domain = domain[len("http://"):]
    return domain


def _bot_public_url(env: Env) -> str:
    host = _normalize_bot_domain(env.str("BOT_DOMAIN", default="localhost"))
    use_https = env.bool("BOT_USE_HTTPS", default=True)
    scheme = "https" if use_https else "http"
    return f"{scheme}://{host}"


def _int_env(env: Env, key: str, default: int = 0) -> int:
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        return default
    return env.int(key)


def _resolve_plans_path(env: Env) -> Path:
    path_str = env.str("PLANS_FILE", default=str(DEFAULT_PLANS_FILE))
    path = Path(path_str)
    if not path.is_absolute():
        path = BASE_DIR.parent / path
    return path


def _read_plans_file(path: Path) -> dict:
    if not path.is_file():
        logger.error("Plans file not found at %s", path)
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _load_plans(env: Env) -> tuple[dict, Path]:
    path = _resolve_plans_path(env)
    return _read_plans_file(path), path


def _parse_inbound_filter(env: Env) -> tuple[str, ...]:
    raw = os.environ.get("XUI_INBOUND_FILTER", "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def load_config() -> Config:
    env = Env()
    env.read_env()

    admins = env.list("BOT_ADMINS", subcast=int, default=[])
    if not admins:
        logger.warning("BOT_ADMINS is empty.")

    admin_chat_id = _int_env(env, "ADMIN_CHAT_ID", default=0)
    if not admin_chat_id and admins:
        admin_chat_id = admins[0]

    xui_token = env.str("XUI_TOKEN", default=None) or None

    bot_port = _int_env(env, "BOT_PORT", default=DEFAULT_BOT_PORT)
    if bot_port in (443, 8443, 80):
        logger.warning(
            "BOT_PORT=%s looks like a public nginx port. "
            "Set BOT_PORT=8090 (internal). Use NGINX_HTTPS_PORT for 8443.",
            bot_port,
        )

    support_username = env.str("SUPPORT_USERNAME", default="nexorasupport").lstrip("@")
    bot_username = env.str("BOT_USERNAME", default="vpn_nexora_bot").lstrip("@")

    plans_data, plans_path = _load_plans(env)
    pricing = PricingConfig(
        TIERS=plans_data,
        REFERRAL_BONUS_TOMAN=_int_env(env, "REFERRAL_BONUS_TOMAN", default=8000),
        REFERRAL_FRIEND_BONUS_TOMAN=_int_env(env, "REFERRAL_FRIEND_BONUS_TOMAN", default=5000),
        QUANTITY_MAX=_int_env(env, "QUANTITY_MAX", default=20),
        plans_file=plans_path,
    )
    if plans_path.is_file():
        pricing._plans_mtime = plans_path.stat().st_mtime

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            USERNAME=bot_username,
            ADMINS=admins,
            DEV_ID=_int_env(env, "BOT_DEV_ID", default=0),
            DOMAIN=_bot_public_url(env),
            PORT=bot_port,
            USE_POLLING=env.bool("BOT_USE_POLLING", default=False),
            REQUIRED_CHANNELS=parse_required_channels(
                env.str("REQUIRED_CHANNELS", default="")
            ),
        ),
        xui=XUIConfig(
            HOST=env.str("XUI_HOST", default="https://p.nexoranode.xyz:2087"),
            PATH=env.str("XUI_PATH", default="/CC6AiFGmYY4ZWVRf08"),
            USERNAME=env.str("XUI_USERNAME"),
            PASSWORD=env.str("XUI_PASSWORD"),
            TOKEN=xui_token,
            SUB_BASE_URL=env.str("XUI_SUB_BASE_URL", default="https://s.nexoranode.xyz:2096/s/"),
            INBOUND_FILTER=_parse_inbound_filter(env),
            START_AFTER_FIRST_USE=env.bool("XUI_START_AFTER_FIRST_USE", default=True),
            DEFAULT_DURATION_DAYS=_int_env(env, "XUI_DEFAULT_DURATION_DAYS", default=30),
            NODE_SYNC_ENABLED=env.bool("NODE_SYNC_ENABLED", default=True),
            NODE_SSH_USER=env.str("NODE_SSH_USER", default="root"),
            NODE_SSH_PORT=_int_env(env, "NODE_SSH_PORT", default=22),
        ),
        database=DatabaseConfig(
            URL=env.str(
                "DATABASE_URL",
                default="sqlite+aiosqlite:////" + str(DEFAULT_DATA_DIR / "nexorabot.sqlite3"),
            ),
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST", default="redis"),
            PORT=_int_env(env, "REDIS_PORT", default=6379),
            DB=env.str("REDIS_DB_NAME", default="0"),
            USERNAME=env.str("REDIS_USERNAME", default=None),
            PASSWORD=env.str("REDIS_PASSWORD", default=None),
        ),
        payment=PaymentConfig(
            CARD_NUMBER=env.str("CARD_NUMBER", default="6037-XXXX-XXXX-XXXX"),
            CARD_OWNER=env.str("CARD_OWNER", default="نکسورانود"),
            CARD_BANK=env.str("CARD_BANK", default="ملت"),
            ADMIN_CHAT_ID=admin_chat_id,
            SUPPORT_USERNAME=support_username,
        ),
        pricing=pricing,
        logging=LoggingConfig(
            LEVEL=env.str("LOG_LEVEL", default="DEBUG"),
            FORMAT=env.str(
                "LOG_FORMAT",
                default="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            ),
        ),
    )
