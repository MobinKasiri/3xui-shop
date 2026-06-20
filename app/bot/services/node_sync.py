"""
Sync VLESS client UUIDs to direct-node xray configs over SSH.

Panel inbounds (Reality + externalProxy) hold client UUIDs; each VPS runs its
own xray and must receive the same UUID list after bot/panel client changes.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
from dataclasses import dataclass

from app.bot.services.xui_api import XUIApiService, XUIError, _parse_json_field

logger = logging.getLogger(__name__)


@dataclass
class DirectNodeTarget:
    inbound_id: int
    remark: str
    domain: str
    node_port: int


async def _resolve_host(domain: str) -> str:
    if domain.replace(".", "").isdigit():
        return domain
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, socket.gethostbyname, domain)


async def _ssh_push_config(
    host: str,
    cfg_b64: str,
    *,
    user: str,
    port: int,
    identity_file: str = "",
) -> bool:
    script = f"""set -euo pipefail
CFG_B64='{cfg_b64}'
mkdir -p /usr/local/etc/xray
printf '%s' "$CFG_B64" | base64 -d > /usr/local/etc/xray/config.json
systemctl daemon-reload
systemctl enable xray 2>/dev/null || true
systemctl restart xray
sleep 2
systemctl is-active --quiet xray
"""
    cmd = [
        "ssh", "-p", str(port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=20",
        "-o", "BatchMode=yes",
    ]
    if identity_file:
        cmd.extend(["-i", identity_file])
    cmd.extend([f"{user}@{host}", "bash", "-s"])
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(script.encode())
    if proc.returncode != 0:
        logger.warning(
            "Node sync SSH failed host=%s: %s",
            host,
            (stderr or stdout).decode(errors="replace")[:600],
        )
        return False
    return True


def _build_node_xray_config(
    clients: list[dict],
    *,
    node_port: int,
    reality: dict,
) -> dict:
    dest = reality.get("dest") or reality.get("target") or "yahoo.com:443"
    snis = reality.get("serverNames") or []
    priv = reality.get("privateKey") or ""
    sids = reality.get("shortIds") or []
    if isinstance(sids, str):
        sids = [sids]

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "vless-reality-in",
            "listen": "0.0.0.0",
            "port": node_port,
            "protocol": "vless",
            "settings": {"clients": clients, "decryption": "none"},
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": False,
                    "dest": dest,
                    "xver": 0,
                    "serverNames": snis,
                    "privateKey": priv,
                    "shortIds": sids,
                },
            },
            "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        }],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}],
        "routing": {"rules": [{"type": "field", "outboundTag": "direct", "network": "tcp,udp"}]},
    }


async def list_direct_node_targets(xui: XUIApiService) -> list[DirectNodeTarget]:
    """Reality inbounds with externalProxy → direct node domain."""
    targets: list[DirectNodeTarget] = []
    for ib in await xui.list_inbounds():
        if not ib.enable or ib.security != "reality":
            continue
        obj = await xui.get_inbound(ib.id)
        stream = _parse_json_field(obj.get("streamSettings"))
        if not isinstance(stream, dict):
            continue
        proxies = stream.get("externalProxy") or []
        if not isinstance(proxies, list) or not proxies:
            continue
        proxy = proxies[0] if isinstance(proxies[0], dict) else {}
        domain = (proxy.get("dest") or "").strip()
        if not domain:
            continue
        targets.append(DirectNodeTarget(
            inbound_id=ib.id,
            remark=ib.remark,
            domain=domain,
            node_port=int(proxy.get("port") or 443),
        ))
    return targets


async def sync_direct_node_inbound(
    xui: XUIApiService,
    target: DirectNodeTarget,
    *,
    ssh_user: str = "root",
    ssh_port: int = 22,
    ssh_identity: str = "",
) -> bool:
    """Push panel inbound clients to the VPS xray config for one direct node."""
    obj = await xui.get_inbound(target.inbound_id)
    stream = _parse_json_field(obj.get("streamSettings"))
    if not isinstance(stream, dict):
        stream = {}
    reality = _parse_json_field(stream.get("realitySettings"))
    if not isinstance(reality, dict):
        reality = {}

    if not reality.get("privateKey") or not reality.get("shortIds"):
        logger.warning(
            "Node sync skip %s — inbound %s missing Reality keys",
            target.domain, target.inbound_id,
        )
        return False

    clients = await xui.get_inbound_vless_clients(target.inbound_id)
    if not clients:
        logger.warning(
            "Node sync skip %s — no VLESS clients with uuid on inbound %s",
            target.domain, target.inbound_id,
        )
        return False

    cfg = _build_node_xray_config(
        clients,
        node_port=target.node_port,
        reality=reality,
    )
    cfg_b64 = base64.b64encode(json.dumps(cfg, separators=(",", ":")).encode()).decode()
    host = await _resolve_host(target.domain)
    ok = await _ssh_push_config(
        host, cfg_b64, user=ssh_user, port=ssh_port, identity_file=ssh_identity,
    )
    if ok:
        logger.info(
            "Node sync OK %s (%s) — %d client(s), uuids=%s",
            target.remark,
            target.domain,
            len(clients),
            [c["id"][:8] + "…" for c in clients],
        )
    return ok


async def sync_all_direct_nodes(
    xui: XUIApiService,
    *,
    ssh_user: str = "root",
    ssh_port: int = 22,
    ssh_identity: str = "",
) -> None:
    """Sync every direct Reality node after panel client changes."""
    try:
        targets = await list_direct_node_targets(xui)
    except XUIError as exc:
        logger.warning("Could not list direct nodes for sync: %s", exc)
        return

    if not targets:
        logger.debug("No direct node inbounds to sync")
        return

    for target in targets:
        try:
            await sync_direct_node_inbound(
                xui,
                target,
                ssh_user=ssh_user,
                ssh_port=ssh_port,
                ssh_identity=ssh_identity,
            )
        except Exception:
            logger.exception("Node sync failed for %s", target.domain)
