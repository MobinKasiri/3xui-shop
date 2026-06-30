#!/usr/bin/env python3
"""Record a confirmed purchase transaction for offline card payment (no panel create).

Run via: ./scripts/record-purchase-transaction.sh

Use when the client is already on the panel and linked in the bot (assign-panel-client.sh),
but no purchase transaction exists for manage-panel revenue.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.services.manual_purchase_tx import record_manual_purchase_transaction
from app.config import load_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Record confirmed purchase transaction (offline payment)"
    )
    p.add_argument("--tg-id", type=int, required=True, help="User Telegram ID")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--email", help="Panel client email (lookup)")
    g.add_argument("--service-name", help="Bot service name (lookup)")
    p.add_argument("--amount", type=int, required=True, help="Paid amount in Toman")
    p.add_argument(
        "--plan-id",
        required=True,
        help="Plan id from plans.json (e.g. vip_30g_30d)",
    )
    p.add_argument(
        "--config-id",
        type=int,
        default=None,
        help="vpn_configs.id (optional if service already assigned)",
    )
    p.add_argument(
        "--payment-method",
        choices=("card", "wallet"),
        default="card",
        help="How the user paid (default: card)",
    )
    p.add_argument("--note", default="", help="Optional note stored in admin_note JSON")
    p.add_argument("--dry-run", action="store_true", help="Validate only")
    p.add_argument(
        "--force",
        action="store_true",
        help="Allow duplicate confirmed tx for same user/service/amount",
    )
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    lookup = (args.service_name or args.email or "").strip()
    if not lookup and args.config_id is None:
        print("Provide --service-name, --email, or --config-id", file=sys.stderr)
        return 1

    config = load_config()
    engine = create_async_engine(config.database.URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            tx = await record_manual_purchase_transaction(
                session,
                config,
                tg_id=args.tg_id,
                service_name=lookup,
                amount=args.amount,
                plan_id=args.plan_id,
                config_id=args.config_id,
                payment_method=args.payment_method,
                admin_note=args.note or None,
                dry_run=args.dry_run,
                allow_duplicate=args.force,
            )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    if args.dry_run:
        print("Dry run OK — would create confirmed purchase transaction:")
    else:
        print("Transaction recorded:")
    print(f"  tx id:          {getattr(tx, 'id', '—')}")
    print(f"  user tg_id:     {args.tg_id}")
    print(f"  service:        {tx.service_name}")
    print(f"  config id:      {tx.config_id}")
    print(f"  amount:         {tx.amount} Toman")
    print(f"  plan_id:        {tx.plan_id}")
    print(f"  status:         {tx.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
