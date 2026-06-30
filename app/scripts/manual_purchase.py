#!/usr/bin/env python3
"""Offline purchase: optionally assign panel client + record confirmed transaction.

Modes (mutually exclusive):
  --assign-only   Link panel client + notify user (no transaction)
  --tx-only       Record transaction only (client must already be assigned)
  (default)       Both: assign (skip if already linked) then record transaction

Run via: ./scripts/manual-purchase.sh
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.services.bootstrap import bootstrap_with_retries, close_xui, ensure_vpn_service
from app.bot.services.manual_assign import assign_panel_client_to_user
from app.bot.services.manual_purchase_tx import record_manual_purchase_transaction
from app.config import load_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manual offline purchase (assign +/or tx)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--assign-only", action="store_true", help="Assign client only")
    mode.add_argument("--tx-only", action="store_true", help="Record transaction only")

    p.add_argument("--tg-id", type=int, required=True)
    p.add_argument(
        "--email",
        default="",
        help="3X-UI panel client email (required for assign step)",
    )
    p.add_argument(
        "--service-name",
        default="",
        help="Bot display name (assign) or lookup key for transaction",
    )

    p.add_argument("--amount", type=int, default=0, help="Required unless --assign-only")
    p.add_argument("--plan-id", default="", help="Required unless --assign-only")
    p.add_argument("--plan-gb", type=int, default=0)
    p.add_argument("--plan-days", type=int, default=30)
    p.add_argument("--plan-name", default="", help="Label in activation message (default: tier name)")
    p.add_argument("--config-id", type=int, default=None)
    p.add_argument("--payment-method", choices=("card", "wallet"), default="card")
    p.add_argument("--note", default="")
    p.add_argument("--no-send", action="store_true", help="Assign without Telegram notify")
    p.add_argument("--no-sync-tg-id", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-tx", action="store_true", help="Allow duplicate transaction")
    p.add_argument(
        "--fail-if-assigned",
        action="store_true",
        help="Do not skip assign when service already linked (default: skip and continue)",
    )
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    panel_email = (args.email or "").strip()
    service_name = (args.service_name or "").strip() or None
    lookup = service_name or panel_email
    if not lookup and args.config_id is None:
        print("Provide --email and/or --service-name (or --config-id for tx)", file=sys.stderr)
        return 1

    do_assign = args.assign_only or not args.tx_only
    do_tx = args.tx_only or not args.assign_only

    if do_assign and not panel_email:
        print("--email (panel client email) is required for assign step", file=sys.stderr)
        return 1

    if do_tx and not args.tx_only:
        if args.amount <= 0 or not args.plan_id:
            print("--amount and --plan-id required for transaction step", file=sys.stderr)
            return 1
    if args.tx_only and (args.amount <= 0 or not args.plan_id):
        print("--tx-only requires --amount and --plan-id", file=sys.stderr)
        return 1

    config = load_config()
    vpn = None
    bot: Bot | None = None

    if do_assign:
        if not await bootstrap_with_retries(config):
            print("Panel bootstrap failed", file=sys.stderr)
            return 1
        vpn = await ensure_vpn_service(config)
        if vpn is None:
            print("VPN service unavailable", file=sys.stderr)
            await close_xui()
            return 1
        if not args.no_send and not args.dry_run:
            bot = Bot(token=config.bot.TOKEN)

    engine = create_async_engine(config.database.URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    assign_result = None
    tx = None

    try:
        async with session_factory() as session:
            if do_assign:
                assert vpn is not None
                try:
                    assign_result = await assign_panel_client_to_user(
                        session,
                        xui=vpn.xui,
                        vpn=vpn,
                        bot=bot,
                        tg_id=args.tg_id,
                        panel_email=panel_email,
                        service_name=service_name,
                        plan_id=args.plan_id or "manual",
                        plan_gb=args.plan_gb,
                        plan_days=args.plan_days,
                        plan_name=args.plan_name,
                        sync_tg_id=not args.no_sync_tg_id,
                        send_notification=not args.no_send,
                        dry_run=args.dry_run,
                    )
                except ValueError as exc:
                    msg = str(exc)
                    if "already linked" in msg or "already has service" in msg:
                        if args.fail_if_assigned:
                            raise
                        print(f"Assign skipped: {msg}")
                    else:
                        raise

            if do_tx:
                tx = await record_manual_purchase_transaction(
                    session,
                    config,
                    tg_id=args.tg_id,
                    service_name=lookup,
                    amount=args.amount,
                    plan_id=args.plan_id,
                    config_id=args.config_id
                    or (assign_result.config.id if assign_result and assign_result.created else None),
                    payment_method=args.payment_method,
                    admin_note=args.note or None,
                    dry_run=args.dry_run,
                    allow_duplicate=args.force_tx,
                )
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if bot:
            await bot.session.close()
        await close_xui()
        await engine.dispose()

    print("Done.")
    if assign_result:
        print(f"  assign:         {'dry-run' if args.dry_run else 'ok'}")
        print(f"  service name:   {assign_result.config.service_name}")
        print(f"  panel email:    {assign_result.config.panel_email}")
        print(f"  config id:      {getattr(assign_result.config, 'id', '—')}")
        print(f"  user notified:  {assign_result.notified}")
    if tx:
        print(f"  transaction:    {'dry-run' if args.dry_run else 'ok'}")
        print(f"  tx id:          {getattr(tx, 'id', '—')}")
        print(f"  amount:         {tx.amount} Toman")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
