"""
Raw async HTTP client for the 3X-UI v3.3.1 panel API.
All endpoints are derived from 3XUI_api.json — never guessed.

Authentication: cookie (POST /login) with auto-relogin on 401.
Optionally uses Bearer token when XUI_TOKEN is set.

All public methods return typed dataclasses or raise one of:
  XUIAuthError, XUINotFound, XUIAPIError, XUINetworkError
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import aiohttp

from app.config import XUIConfig

logger = logging.getLogger(__name__)


# ─── Custom exceptions ────────────────────────────────────────────────────────

class XUIError(Exception):
    """Base XUI exception."""
    persian: str = "خطایی رخ داد. لطفاً دوباره تلاش کنید."


class XUIAuthError(XUIError):
    persian = "⚠️ خطا در احراز هویت پنل. با پشتیبانی تماس بگیرید."


class XUINotFound(XUIError):
    persian = "❌ سرویس مورد نظر یافت نشد."


class XUIAPIError(XUIError):
    persian = "⚠️ خطا در ارتباط با سرور. لطفاً دقایقی دیگر تلاش کنید."


class XUINetworkError(XUIError):
    persian = "⚠️ اتصال به سرور برقرار نشد. اینترنت سرور را بررسی کنید."


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class InboundInfo:
    id: int
    remark: str
    protocol: str
    port: int
    enable: bool


@dataclass
class ClientTraffic:
    email: str
    up: int
    down: int
    total: int           # traffic limit in bytes (0 = unlimited)
    expiry_time: int     # ms timestamp (0 = never)
    enable: bool

    @property
    def used_bytes(self) -> int:
        return self.up + self.down

    @property
    def expiry_dt(self) -> datetime | None:
        if self.expiry_time == 0:
            return None
        return datetime.fromtimestamp(self.expiry_time / 1000, tz=timezone.utc)


@dataclass
class ServerStatus:
    cpu: float
    mem_current: int
    mem_total: int
    uptime: int
    xray_state: str


@dataclass
class ClientAddPayload:
    """Everything needed to create a client on the panel."""
    email: str
    uuid: str           # VLESS/VMess id
    sub_id: str         # subscription ID (same UUID)
    total_bytes: int    # 0 = unlimited
    expiry_ms: int      # ms timestamp; 0 = never
    flow: str           # "" for WS, "xtls-rprx-vision" for Reality
    inbound_ids: list[int]
    limit_ip: int = 0
    enable: bool = True
    tg_id: int = 0


# ─── XUI API Client ──────────────────────────────────────────────────────────

class XUIApiService:
    def __init__(self, config: XUIConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._logged_in = False

    @property
    def _base(self) -> str:
        return self._config.base_url

    @staticmethod
    def _email_path(email: str) -> str:
        """URL-encode client email for use in path segments (contains @)."""
        return quote(email, safe="")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            headers = {}
            if self._config.TOKEN:
                headers["Authorization"] = f"Bearer {self._config.TOKEN}"
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                headers=headers,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def login(self) -> None:
        """Authenticate via cookie. Raises XUIAuthError on failure."""
        session = await self._get_session()

        # Browser panel sends username + password as form-urlencoded only.
        form_payload = {
            "username": self._config.USERNAME,
            "password": self._config.PASSWORD,
        }
        json_payload = {**form_payload, "twoFactorCode": ""}

        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Origin": self._config.HOST.rstrip("/"),
            "Referer": self._base.rstrip("/") + "/",
        }

        login_url = self._base.rstrip("/") + "/login"
        last_error = "unknown"
        saw_403 = False
        try:
            # Form-urlencoded first — matches browser DevTools "Form Data"
            for mode, kwargs in (
                ("form", {"data": form_payload}),
                ("json", {"json": json_payload}),
            ):
                try:
                    async with session.post(
                        login_url, headers=browser_headers, **kwargs
                    ) as resp:
                        body_text = await resp.text()
                        data = None
                        try:
                            data = json.loads(body_text)
                        except Exception:
                            pass

                        if data and data.get("success"):
                            self._logged_in = True
                            logger.info(
                                "3X-UI login OK — url=%s mode=%s",
                                login_url, mode,
                            )
                            return

                        msg = (data or {}).get("msg") if data else body_text[:300]
                        last_error = f"{login_url} [{mode}] HTTP {resp.status}: {msg}"
                        logger.warning("Login attempt failed: %s", last_error)
                        if resp.status == 403:
                            saw_403 = True

                except aiohttp.ClientError as e:
                    last_error = f"{login_url} [{mode}]: {e}"

            if saw_403:
                raise XUIAuthError(
                    f"Login blocked (HTTP 403) at {login_url}. "
                    "Set XUI_TOKEN in .env (Panel → Settings → Security → API Token) "
                    "or allow the bot server IP in panel/nginx."
                )
            raise XUIAuthError(f"Login failed: {last_error}")
        except XUIAuthError:
            raise
        except aiohttp.ClientError as e:
            raise XUINetworkError(str(e)) from e

    async def _request(
        self, method: str, path: str, *, retry: bool = True, **kwargs: Any
    ) -> dict:
        """Make an authenticated request; auto-relogin on 401."""
        if not self._logged_in and not self._config.TOKEN:
            await self.login()
        session = await self._get_session()
        url = f"{self._base}{path}"
        try:
            async with session.request(method, url, **kwargs) as resp:
                if resp.status == 401:
                    if self._config.TOKEN:
                        raise XUIAuthError("Invalid or expired API token.")
                    if retry:
                        self._logged_in = False
                        await self.login()
                        return await self._request(method, path, retry=False, **kwargs)
                    raise XUIAuthError("Persistent 401 after relogin.")
                if resp.status == 404:
                    raise XUINotFound(f"404 on {path}")
                body_text = await resp.text()
                try:
                    data = json.loads(body_text) if body_text else {}
                except json.JSONDecodeError:
                    raise XUIAPIError(
                        f"Non-JSON response on {path}: HTTP {resp.status} — {body_text[:300]}"
                    )
                if not data.get("success", True):
                    raise XUIAPIError(f"API error on {path}: {data.get('msg', body_text[:200])}")
                return data
        except (XUIAuthError, XUINotFound, XUIAPIError):
            raise
        except aiohttp.ClientError as e:
            raise XUINetworkError(str(e)) from e

    # ── Inbounds ──────────────────────────────────────────────────────────────

    async def list_inbounds(self) -> list[InboundInfo]:
        """GET /panel/api/inbounds/list"""
        data = await self._request("GET", "/panel/api/inbounds/list")
        result = []
        for item in data.get("obj", []):
            result.append(InboundInfo(
                id=item["id"],
                remark=item.get("remark", ""),
                protocol=item.get("protocol", ""),
                port=item.get("port", 0),
                enable=item.get("enable", True),
            ))
        return result

    async def enabled_inbound_ids(
        self, filter_names: tuple[str, ...] = ()
    ) -> list[int]:
        """Return IDs of all enabled inbounds (optional name filter)."""
        inbounds = await self.list_inbounds()
        enabled = [ib for ib in inbounds if ib.enable]

        if not enabled:
            raise XUINotFound("No enabled inbounds on panel.")

        def _norm(s: str) -> str:
            return " ".join(s.split())

        if filter_names:
            filters = {_norm(name) for name in filter_names}
            selected = [ib for ib in enabled if _norm(ib.remark) in filters]
            if not selected:
                available = [ib.remark for ib in enabled]
                raise XUINotFound(
                    f"Inbound filter {list(filter_names)} matched nothing. "
                    f"Enabled inbounds: {available}"
                )
        else:
            selected = enabled

        ids = [ib.id for ib in selected]
        logger.info(
            "Enabled inbounds selected: %s",
            [(ib.id, ib.remark, ib.port) for ib in selected],
        )
        return ids

    # ── Clients ───────────────────────────────────────────────────────────────

    async def add_client(self, payload: ClientAddPayload) -> dict:
        """
        POST /panel/api/clients/add
        Creates the client and attaches it to inbound_ids in one call.
        """
        client: dict[str, Any] = {
            "email": payload.email,
            "subId": payload.sub_id,
            "totalGB": payload.total_bytes,
            "expiryTime": payload.expiry_ms,
            "tgId": payload.tg_id,
            "limitIp": payload.limit_ip,
            "enable": payload.enable,
            "comment": "",
            "reset": 0,
        }
        if payload.uuid:
            client["id"] = payload.uuid
        if payload.flow:
            client["flow"] = payload.flow

        body = {"client": client, "inboundIds": payload.inbound_ids}
        logger.info("XUI add_client: email=%s inbounds=%s", payload.email, payload.inbound_ids)
        data = await self._request("POST", "/panel/api/clients/add", json=body)
        # obj is often null on success — subscription data is built locally from subId
        logger.info(
            "Client created: %s on inbounds %s (msg=%s)",
            payload.email,
            payload.inbound_ids,
            data.get("msg", ""),
        )
        return data

    async def bulk_attach(self, emails: list[str], inbound_ids: list[int]) -> None:
        """POST /panel/api/clients/bulkAttach"""
        await self._request(
            "POST",
            "/panel/api/clients/bulkAttach",
            json={"emails": emails, "inboundIds": inbound_ids},
        )
        logger.info("Clients %s attached to inbounds %s", emails, inbound_ids)

    async def update_client(
        self,
        email: str,
        *,
        total_bytes: int,
        expiry_ms: int,
        flow: str = "",
        limit_ip: int = 0,
        enable: bool = True,
        tg_id: int = 0,
        sub_id: str | None = None,
    ) -> None:
        """
        POST /panel/api/clients/update/{email}
        Full replace — all fields required.
        """
        body: dict[str, Any] = {
            "email": email,
            "totalGB": total_bytes,
            "expiryTime": expiry_ms,
            "flow": flow,
            "limitIp": limit_ip,
            "enable": enable,
            "tgId": tg_id,
        }
        if sub_id is not None:
            body["subId"] = sub_id
        await self._request(
            "POST",
            f"/panel/api/clients/update/{self._email_path(email)}",
            json=body,
        )
        logger.info(f"Client updated: {email}")

    async def set_client_enabled(self, email: str, enabled: bool) -> None:
        """
        Toggle a client's enable flag while preserving traffic and expiry.
        Uses /panel/api/clients/update/{email} with the live values.
        """
        traffic = await self.get_client_traffic(email)
        await self.update_client(
            email,
            total_bytes=traffic.total,
            expiry_ms=traffic.expiry_time,
            enable=enabled,
        )
        logger.info(f"Client {email} enabled={enabled}")

    async def reset_subscription(self, email: str, new_sub_id: str) -> None:
        """Reset a client's subscription id while preserving traffic/expiry."""
        traffic = await self.get_client_traffic(email)
        await self.update_client(
            email,
            total_bytes=traffic.total,
            expiry_ms=traffic.expiry_time,
            enable=traffic.enable,
            sub_id=new_sub_id,
        )
        logger.info(f"Client {email} sub_id reset")

    async def get_inbound(self, inbound_id: int) -> dict:
        """GET /panel/api/inbounds/get/{id} — returns the full inbound payload."""
        data = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        return data.get("obj") or {}

    async def delete_client(self, email: str) -> None:
        """POST /panel/api/clients/del/{email}?keepTraffic=0"""
        await self._request(
            "POST",
            f"/panel/api/clients/del/{self._email_path(email)}",
            params={"keepTraffic": 0},
        )
        logger.info(f"Client deleted: {email}")

    async def get_client_traffic(self, email: str) -> ClientTraffic:
        """GET /panel/api/clients/traffic/{email}"""
        data = await self._request(
            "GET", f"/panel/api/clients/traffic/{self._email_path(email)}"
        )
        obj = data.get("obj") or {}
        if not obj:
            raise XUINotFound(f"No traffic data for {email}")
        return ClientTraffic(
            email=obj.get("email", email),
            up=obj.get("up", 0),
            down=obj.get("down", 0),
            total=obj.get("total", 0),
            expiry_time=obj.get("expiryTime", 0),
            enable=obj.get("enable", True),
        )

    async def get_client_links(self, email: str) -> list[str]:
        """GET /panel/api/clients/links/{email} — returns list of protocol URLs."""
        data = await self._request("GET", f"/panel/api/clients/links/{self._email_path(email)}")
        obj = data.get("obj", [])
        if isinstance(obj, list):
            return obj
        return []

    async def get_sub_links(self, sub_id: str) -> list[str]:
        """GET /panel/api/clients/subLinks/{subId}"""
        data = await self._request("GET", f"/panel/api/clients/subLinks/{sub_id}")
        obj = data.get("obj", [])
        if isinstance(obj, list):
            return obj
        return []

    async def attach_client(self, email: str, inbound_ids: list[int]) -> None:
        """POST /panel/api/clients/{email}/attach"""
        await self._request(
            "POST",
            f"/panel/api/clients/{self._email_path(email)}/attach",
            json={"inboundIds": inbound_ids},
        )
        logger.info(f"Client {email} attached to inbounds {inbound_ids}")

    async def detach_client(self, email: str, inbound_ids: list[int]) -> None:
        """POST /panel/api/clients/{email}/detach"""
        await self._request(
            "POST",
            f"/panel/api/clients/{self._email_path(email)}/detach",
            json={"inboundIds": inbound_ids},
        )
        logger.info(f"Client {email} detached from inbounds {inbound_ids}")

    # ── Server ────────────────────────────────────────────────────────────────

    async def get_server_status(self) -> ServerStatus:
        """GET /panel/api/server/status"""
        data = await self._request("GET", "/panel/api/server/status")
        obj = data.get("obj", {}) or {}
        mem = obj.get("mem") or {}
        if isinstance(mem, dict):
            mem_current = mem.get("current", 0)
            mem_total = mem.get("total", 1)
        else:
            mem_current = int(mem) if mem else 0
            mem_total = 1
        xray = obj.get("xray") or {}
        xray_state = xray.get("state", "unknown") if isinstance(xray, dict) else str(xray)
        return ServerStatus(
            cpu=float(obj.get("cpu", 0.0) or 0.0),
            mem_current=mem_current,
            mem_total=mem_total or 1,
            uptime=int(obj.get("uptime", 0) or 0),
            xray_state=xray_state,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        logger.debug("XUI API session closed.")
