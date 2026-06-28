#!/usr/bin/env python3
"""Assign an existing 3X-UI panel client to a bot user and send config (like purchase approve).

Workflow:
  1. Create the client manually in 3X-UI (email = service name, e.g. ``ali123``).
  2. Set traffic, expiry, subscription ID (subId), attach inbounds.
  3. Run this script with the user's Telegram ID from the admin panel.

Usage:
  cd /opt/nexoranode-bot

  # Preview only
  python3 scripts/assign_panel_client.py --tg-id 123456789 --email ali123 --dry-run

  # Assign + send QR + sub link to user (same as approved purchase)
  python3 scripts/assign_panel_client.py --tg-id 123456789 --email ali123

  # Custom plan metadata shown in the activation message
  python3 scripts/assign_panel_client.py --tg-id 123456789 --email ali123 \\
      --plan-gb 30 --plan-days 30 --plan-id vip_30 --plan-name VIP

  # Link in DB only — no Telegram message
  python3 scripts/assign_panel_client.py --tg-id 123456789 --email ali123 --no-send
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.services.bootstrap import bootstrap_with_retries, close_xui, ensure_vpn_service
from app.bot.services.manual_assign import assign_panel_client_to_user
from app.config import load_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assign panel client to bot user")
    p.add_argument(
        "--tg-id",
        type=int,
        required=True,
        help="Telegram user ID (from admin manage panel)",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--email", help="Panel client email / service name (e.g. ali123)")
    g.add_argument("--service-name", help="Alias for --email")
    p.add_argument("--plan-id", default="manual", help="Stored plan_id (default: manual)")
    p.add_argument("--plan-gb", type=int, default=0, help="Plan GB if panel total is 0")
    p.add_argument("--plan-days", type=int, default=30, help="Plan days for delayed-start text")
    p.add_argument("--plan-name", default="VIP", help="Label in activation message")
    p.add_argument(
        "--no-send",
        action="store_true",
        help="Create DB row only — do not message the user",
    )
    p.add_argument(
        "--no-sync-tg-id",
        action="store_true",
        help="Do not write user's tg_id onto the panel client",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate panel + user only; no DB write, no Telegram",
    )
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    service_name = (args.email or args.service_name or "").strip()
    if not service_name:
        print("Provide --email or --service-name", file=sys.stderr)
        return 1

    config = load_config()
    if not await bootstrap_with_retries(config):
        print("Panel bootstrap failed — check XUI_* in .env", file=sys.stderr)
        return 1

    vpn = await ensure_vpn_service(config)
    if vpn is None:
        print("VPN service unavailable", file=sys.stderr)
        await close_xui()
        return 1

    bot: Bot | None = None
    if not args.no_send and not args.dry_run:
        bot = Bot(token=config.bot.TOKEN)

    engine = create_async_engine(config.database.URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            result = await assign_panel_client_to_user(
                session,
                xui=vpn.xui,
                vpn=vpn,
                bot=bot,
                tg_id=args.tg_id,
                service_name=service_name,
                plan_id=args.plan_id,
                plan_gb=args.plan_gb,
                plan_days=args.plan_days,
                plan_name=args.plan_name,
                sync_tg_id=not args.no_sync_tg_id,
                send_notification=not args.no_send,
                dry_run=args.dry_run,
            )
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if bot:
            await bot.session.close()
        await close_xui()
        await engine.dispose()

    cfg = result.config
    if args.dry_run:
        print("Dry run OK — would assign:")
    else:
        print("Assigned successfully:")
    print(f"  user tg_id:     {args.tg_id}")
    print(f"  service:        {cfg.service_name}")
    print(f"  config id:      {getattr(cfg, 'id', '—')}")
    print(f"  plan:           {cfg.plan_gb} GB / {cfg.plan_days} days")
    print(f"  subscription:   {result.sub_url}")
    if not args.dry_run:
        print(f"  user notified:  {result.notified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
