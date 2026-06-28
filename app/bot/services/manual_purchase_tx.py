"""Record a confirmed purchase transaction for offline / manual card payments.

Does NOT create panel clients — link an existing config via config_id or service email.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.utils.persian import to_persian_digits
from app.bot.utils.service_name import panel_email, validate
from app.config import Config
from app.db.models import User, VPNConfig
from app.db.models.transaction import (
    PAY_CARD,
    PAY_WALLET,
    TX_CONFIRMED,
    TX_PURCHASE,
    Transaction,
)

logger = logging.getLogger(__name__)

_PAY_METHODS = {PAY_CARD, PAY_WALLET}


def _resolve_plan(config: Config, plan_id: str) -> dict:
    plan = config.pricing.get_plan(plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id!r} not found in plans.json")
    return plan


async def _resolve_config(
    session: AsyncSession,
    *,
    tg_id: int,
    service_name: str,
    config_id: int | None,
) -> VPNConfig:
    if config_id is not None:
        cfg = await VPNConfig.get(session, config_id)
        if not cfg:
            raise ValueError(f"vpn_configs.id={config_id} not found")
        if cfg.user_id != tg_id:
            raise ValueError(
                f"Config {config_id} belongs to user {cfg.user_id}, not {tg_id}"
            )
        return cfg

    email = panel_email(service_name)
    cfg = await VPNConfig.get_by_email(session, email)
    if cfg:
        if cfg.user_id != tg_id:
            raise ValueError(
                f"Service {email!r} belongs to user {cfg.user_id}, not {tg_id}"
            )
        return cfg

    cfg = await VPNConfig.get_by_name(session, tg_id, email)
    if cfg:
        return cfg

    raise ValueError(
        f"No bot config for {email!r} / user {tg_id}. "
        "Run assign-panel-client.sh first or pass --config-id"
    )


async def _find_duplicate_tx(
    session: AsyncSession,
    *,
    user_id: int,
    service_name: str,
    amount: int,
    config_id: int | None,
) -> Transaction | None:
    q = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.type == TX_PURCHASE)
        .where(Transaction.status == TX_CONFIRMED)
        .where(Transaction.amount == amount)
        .order_by(Transaction.confirmed_at.desc())
        .limit(5)
    )
    rows = list((await session.execute(q)).scalars().all())
    email = panel_email(service_name)
    for tx in rows:
        if tx.config_id and config_id and tx.config_id == config_id:
            return tx
        if tx.service_name and tx.service_name.lower() == email:
            return tx
    return None


async def record_manual_purchase_transaction(
    session: AsyncSession,
    config: Config,
    *,
    tg_id: int,
    service_name: str,
    amount: int,
    plan_id: str,
    config_id: int | None = None,
    payment_method: str = PAY_CARD,
    admin_note: str | None = None,
    dry_run: bool = False,
    allow_duplicate: bool = False,
) -> Transaction:
    """
    Insert a **confirmed** purchase row so manage-panel revenue / reports include
    offline card payments. Never touches the 3X-UI panel.
    """
    if amount <= 0:
        raise ValueError("--amount must be positive (Toman)")

    email = panel_email(service_name)
    if not validate(email):
        raise ValueError(f"Invalid service name {service_name!r}")

    user = await User.get(session, tg_id)
    if not user:
        raise ValueError(f"User tg_id={tg_id} not found — user must /start the bot")

    if payment_method not in _PAY_METHODS:
        raise ValueError(f"payment_method must be one of {_PAY_METHODS}")

    plan = _resolve_plan(config, plan_id)
    cfg = await _resolve_config(
        session, tg_id=tg_id, service_name=email, config_id=config_id
    )

    dup = await _find_duplicate_tx(
        session,
        user_id=tg_id,
        service_name=email,
        amount=amount,
        config_id=cfg.id,
    )
    if dup and not allow_duplicate:
        raise ValueError(
            f"Duplicate confirmed purchase tx id={dup.id} "
            f"(user={tg_id} service={email} amount={amount}). Use --force to add anyway."
        )

    tier_name = plan.get("tier_name") or "VIP"
    description = fa.TX_DESC_PURCHASE.format(
        plan_name=tier_name,
        qty=to_persian_digits(1),
        name=cfg.service_name,
    )

    note_payload = {
        "manual": True,
        "offline_payment": True,
        "skip_panel_create": True,
        "plan_id": plan_id,
        "plan_gb": plan.get("gb"),
        "plan_days": plan.get("days"),
        "service_names": [cfg.service_name],
        "config_id": cfg.id,
    }
    if admin_note:
        note_payload["note"] = admin_note

    if dry_run:
        logger.info("Dry run — would create confirmed purchase tx for config %s", cfg.id)
        return Transaction(
            user_id=tg_id,
            amount=amount,
            payment_amount=amount,
            type=TX_PURCHASE,
            description=description,
            config_id=cfg.id,
            plan_id=plan_id,
            quantity=1,
            service_name=cfg.service_name,
            payment_method=payment_method,
            status=TX_CONFIRMED,
            admin_note=json.dumps(note_payload, ensure_ascii=False),
        )

    now = datetime.utcnow()
    tx = await Transaction.create(
        session,
        user_id=tg_id,
        amount=amount,
        payment_amount=amount,
        type=TX_PURCHASE,
        description=description,
        config_id=cfg.id,
        plan_id=plan_id,
        quantity=1,
        service_name=cfg.service_name,
        payment_method=payment_method,
        status=TX_CONFIRMED,
        confirmed_at=now,
        admin_note=json.dumps(note_payload, ensure_ascii=False),
    )
    logger.info(
        "Manual purchase tx %s recorded user=%s config=%s amount=%s",
        tx.id,
        tg_id,
        cfg.id,
        amount,
    )
    return tx
