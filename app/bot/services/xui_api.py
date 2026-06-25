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

from app.xui_config import XUIConfig

logger = logging.getLogger(__name__)

REALITY_FLOW = "xtls-rprx-vision"
_INBOUND_UPDATE_SKIP = frozenset({
    "id", "up", "down", "clientStats", "tag", "subSortIndex",
    "lastTrafficResetTime", "trafficReset",
})


def _parse_json_field(val: Any) -> dict | list | Any:
    if isinstance(val, str):
        if not val.strip():
            return {}
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    return val if val is not None else {}


def _inbound_security(stream_settings: Any) -> str:
    stream = _parse_json_field(stream_settings)
    if isinstance(stream, dict):
        return str(stream.get("security") or "")
    return ""


def _inbound_update_payload(obj: dict, settings: dict, stream_settings: dict) -> dict:
    payload = {k: v for k, v in obj.items() if k not in _INBOUND_UPDATE_SKIP}
    payload["settings"] = settings
    payload["streamSettings"] = stream_settings
    return payload


def extract_vless_uuid(record: dict) -> str:
    """VLESS UUID from a client record (handles v3.3 nested shapes)."""
    if not isinstance(record, dict):
        return ""
    for key in ("uuid", "UUID"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Some endpoints expose the VLESS secret as string id (not numeric row id).
    val = record.get("id")
    if isinstance(val, str) and "-" in val:
        return val.strip()
    return ""


def _unwrap_client_obj(obj: Any) -> dict:
    """3X-UI v3.3 GET /clients/get returns {client, inboundIds}, not a flat client."""
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get("client"), dict):
        merged = dict(obj["client"])
        if "inboundIds" in obj:
            merged["inboundIds"] = obj["inboundIds"]
        return merged
    return obj


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
    security: str = ""  # "reality", "tls", "none", ...


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
    comment: str = ""

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
                security=_inbound_security(item.get("streamSettings")),
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

    async def get_client(self, email: str) -> dict:
        """GET /panel/api/clients/get/{email} — includes uuid + inboundIds."""
        data = await self._request(
            "GET", f"/panel/api/clients/get/{self._email_path(email)}"
        )
        return _unwrap_client_obj(data.get("obj"))

    async def resolve_client_uuid(self, email: str, *, hint: str = "") -> str:
        """Fetch VLESS uuid after create — tries get, list, then hint."""
        record = await self.get_client(email)
        uuid_val = extract_vless_uuid(record)
        if uuid_val:
            return uuid_val

        data = await self._request("GET", "/panel/api/clients/list")
        for item in data.get("obj") or []:
            if isinstance(item, dict) and item.get("email") == email:
                uuid_val = extract_vless_uuid(item)
                if uuid_val:
                    return uuid_val

        if hint:
            return hint.strip()
        return ""

    async def add_client(self, payload: ClientAddPayload) -> dict:
        """
        POST /panel/api/clients/add
        Creates the client and attaches it to inbound_ids in one call.

        VLESS secret must be sent as ``uuid`` (panel DB field). The numeric
        client row id is ``id`` — never put the VLESS UUID in ``id``.
        """
        client: dict[str, Any] = {
            "email": payload.email,
            "subId": payload.sub_id,
            "totalGB": payload.total_bytes,
            "expiryTime": payload.expiry_ms,
            "tgId": payload.tg_id,
            "limitIp": payload.limit_ip,
            "enable": payload.enable,
            "comment": payload.comment or "",
            "reset": 0,
        }
        if payload.uuid:
            client["uuid"] = payload.uuid
        # Do NOT set client["id"] — that is the numeric DB row id in 3X-UI v3.3+
        if payload.flow:
            client["flow"] = payload.flow

        body = {"client": client, "inboundIds": payload.inbound_ids}
        logger.info(
            "XUI add_client: email=%s uuid=%s inbounds=%s",
            payload.email, payload.uuid, payload.inbound_ids,
        )
        data = await self._request("POST", "/panel/api/clients/add", json=body)
        logger.info(
            "Client created: %s on inbounds %s (msg=%s)",
            payload.email,
            payload.inbound_ids,
            data.get("msg", ""),
        )
        return data

    async def ensure_subscription_settings(self, *, sub_base_url: str = "") -> None:
        """Subscription panel: clean names + optional Iran routing on standard /s/ sub."""
        try:
            data = await self._request("POST", "/panel/api/setting/all")
        except XUIError as exc:
            logger.warning("Could not read panel settings: %s", exc)
            return
        settings = data.get("obj") or {}
        if not isinstance(settings, dict):
            return
        changed = False
        if settings.get("subShowInfo"):
            settings["subShowInfo"] = False
            changed = True
        if settings.get("subEmailInRemark"):
            settings["subEmailInRemark"] = False
            changed = True
        if settings.get("remarkModel") != "-i":
            settings["remarkModel"] = "-i"
            changed = True
        from app.bot.utils.sub_url import DEFAULT_ROUTING_RULES

        if not settings.get("subEnableRouting"):
            settings["subEnableRouting"] = True
            changed = True
        routing = (settings.get("subRoutingRules") or "").strip()
        if not routing:
            settings["subRoutingRules"] = DEFAULT_ROUTING_RULES
            changed = True
        if sub_base_url:
            sub_uri = sub_base_url.rstrip("/") + "/"
            if settings.get("subURI") != sub_uri:
                settings["subURI"] = sub_uri
                changed = True
        if changed:
            try:
                await self._request("POST", "/panel/api/setting/update", json=settings)
                logger.info(
                    "Panel subscription: routing=%s subURI=%s",
                    settings.get("subEnableRouting"),
                    settings.get("subURI", ""),
                )
            except XUIError as exc:
                logger.warning("Could not update panel subscription settings: %s", exc)
        else:
            logger.info(
                "Panel subscription OK — routing=%s subURI=%s",
                settings.get("subEnableRouting"),
                settings.get("subURI") or "(empty)",
            )

    async def ensure_clean_subscription_names(self) -> None:
        """Backward-compatible alias."""
        await self.ensure_subscription_settings()

    async def get_inbound_vless_clients(self, inbound_id: int) -> list[dict]:
        """
        Xray client entries for a direct node — uuid always from central client record.
        Inbound settings.clients may omit ``id`` for API-created clients (v3.3+).
        """
        obj = await self.get_inbound(inbound_id)
        stream = _parse_json_field(obj.get("streamSettings"))
        security = stream.get("security", "") if isinstance(stream, dict) else ""
        default_flow = REALITY_FLOW if security == "reality" else ""

        settings = _parse_json_field(obj.get("settings"))
        embedded = settings.get("clients") if isinstance(settings, dict) else []
        if not isinstance(embedded, list):
            embedded = []

        out: list[dict] = []
        for c in embedded:
            email = (c.get("email") or "").strip()
            if not email:
                continue
            try:
                record = await self.get_client(email)
            except XUIError:
                record = {}
            vless_id = extract_vless_uuid(record) or (
                (c.get("id") if isinstance(c.get("id"), str) else "") or c.get("uuid") or ""
            ).strip()
            if not vless_id:
                logger.warning("Skipping %s on inbound %s — no VLESS uuid", email, inbound_id)
                continue
            flow = c.get("flow") or default_flow
            entry: dict[str, Any] = {"id": vless_id, "email": email}
            if flow:
                entry["flow"] = flow
            out.append(entry)
        return out

    async def ensure_client_on_inbounds(
        self, email: str, vless_uuid: str, inbound_ids: list[int], *, enable: bool | None = None
    ) -> None:
        """Force client into every inbound settings + correct uuid/flow (like panel UI)."""
        if inbound_ids:
            try:
                await self.bulk_attach([email], inbound_ids)
            except XUIError as exc:
                logger.warning("bulkAttach for %s (non-fatal): %s", email, exc)
        await self.finalize_client_on_inbounds(email, vless_uuid, inbound_ids, enable=enable)

    async def update_inbound(self, inbound_id: int, body: dict) -> None:
        """POST /panel/api/inbounds/update/{id}"""
        await self._request(
            "POST",
            f"/panel/api/inbounds/update/{inbound_id}",
            json=body,
        )

    async def patch_client_on_inbound(
        self, inbound_id: int, email: str, vless_uuid: str, *, enable: bool | None = None
    ) -> None:
        """
        Ensure inbound settings.clients[] has the canonical VLESS uuid + correct flow.
        Inbound client objects use ``id`` for the VLESS UUID string.
        """
        obj = await self.get_inbound(inbound_id)
        stream = _parse_json_field(obj.get("streamSettings"))
        if not isinstance(stream, dict):
            stream = {}
        security = stream.get("security", "")
        flow = REALITY_FLOW if security == "reality" else ""

        settings = _parse_json_field(obj.get("settings"))
        if not isinstance(settings, dict):
            settings = {}
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            clients = []

        touched = False
        for client in clients:
            if client.get("email") != email:
                continue
            if client.get("id") != vless_uuid:
                client["id"] = vless_uuid
                touched = True
            want_flow = flow
            if client.get("flow", "") != want_flow:
                client["flow"] = want_flow
                touched = True
            if enable is not None and client.get("enable") is not enable:
                client["enable"] = enable
                touched = True
            break
        else:
            # Client attached in DB but missing from inbound JSON — inject entry.
            clients.append({
                "email": email,
                "id": vless_uuid,
                "flow": flow,
                "enable": True if enable is None else enable,
            })
            settings["clients"] = clients
            touched = True

        if not touched:
            return

        payload = _inbound_update_payload(obj, settings, stream)
        await self.update_inbound(inbound_id, payload)
        logger.info(
            "Patched inbound %s client %s uuid=%s flow=%r enable=%s",
            inbound_id, email, vless_uuid, flow, enable,
        )

    async def finalize_client_on_inbounds(
        self, email: str, vless_uuid: str, inbound_ids: list[int], *, enable: bool | None = None
    ) -> None:
        """Sync VLESS uuid + per-inbound flow/enable on every attached inbound."""
        for ib_id in inbound_ids:
            try:
                await self.patch_client_on_inbound(ib_id, email, vless_uuid, enable=enable)
            except XUIError as exc:
                logger.warning(
                    "Inbound patch failed for %s inbound %s: %s",
                    email, ib_id, exc,
                )

    async def apply_client_flows(self, email: str, inbound_ids: list[int]) -> None:
        """Sync panel uuid + per-inbound flow on every attached inbound."""
        record = await self.get_client(email)
        vless_uuid = record.get("uuid") or ""
        if not vless_uuid:
            logger.warning("No panel uuid for %s after create — inbound links may fail", email)
            return
        await self.finalize_client_on_inbounds(email, vless_uuid, inbound_ids)

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
        comment: str | None = None,
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
        if comment is not None:
            body["comment"] = comment
        if sub_id is not None:
            body["subId"] = sub_id
        await self._request(
            "POST",
            f"/panel/api/clients/update/{self._email_path(email)}",
            json=body,
        )
        logger.info(f"Client updated: {email}")

    @staticmethod
    def _client_fields_for_update(
        record: dict,
        traffic: ClientTraffic,
        **overrides: Any,
    ) -> dict[str, Any]:
        """Build a full clients/update body (panel replaces the row; do not omit fields)."""
        fields: dict[str, Any] = {
            "total_bytes": traffic.total,
            "expiry_ms": traffic.expiry_time,
            "flow": record.get("flow") or "",
            "limit_ip": int(record.get("limitIp") or 0),
            "enable": bool(record.get("enable", True)),
            "tg_id": int(record.get("tgId") or 0),
            "sub_id": record.get("subId"),
            "comment": record.get("comment"),
        }
        fields.update(overrides)
        return fields

    async def set_client_enabled(self, email: str, enabled: bool) -> None:
        """
        Toggle a client's enable flag while preserving traffic and expiry.
        Updates central clients DB and syncs enable on every attached inbound.
        """
        record = await self.get_client(email)
        traffic = await self.get_client_traffic(email)
        await self.update_client(
            email,
            **self._client_fields_for_update(record, traffic, enable=enabled),
        )
        vless_uuid = extract_vless_uuid(record)
        inbound_ids: list[int] = []
        for raw in record.get("inboundIds") or []:
            try:
                inbound_ids.append(int(raw))
            except (TypeError, ValueError):
                pass
        if vless_uuid and inbound_ids:
            await self.finalize_client_on_inbounds(
                email, vless_uuid, inbound_ids, enable=enabled
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

    @staticmethod
    def _match_client_email(candidate: str, target: str) -> bool:
        return (candidate or "").strip().lower() == (target or "").strip().lower()

    async def find_client_records(self, email: str) -> list[dict]:
        """Return all panel rows matching this client email (central clients API)."""
        email = email.strip()
        found: list[dict] = []
        seen: set[str] = set()

        def _add(row: dict) -> None:
            em = (row.get("email") or "").strip()
            if not em or em in seen:
                return
            if self._match_client_email(em, email):
                seen.add(em)
                found.append(row)

        try:
            _add(await self.get_client(email))
        except XUINotFound:
            pass

        try:
            data = await self._request("GET", "/panel/api/clients/list")
            for item in data.get("obj") or []:
                if isinstance(item, dict):
                    _add(item)
        except XUIError as exc:
            logger.warning("clients/list lookup for %s: %s", email, exc)

        try:
            data = await self._request(
                "GET",
                "/panel/api/clients/list/paged",
                params={
                    "page": 1,
                    "pageSize": 50,
                    "search": email,
                    "filter": "",
                    "protocol": "",
                    "sort": "email",
                    "order": "desc",
                },
            )
            obj = data.get("obj") or {}
            items = obj.get("items") if isinstance(obj, dict) else obj
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        _add(item)
        except XUIError as exc:
            logger.warning("clients/list/paged lookup for %s: %s", email, exc)

        return found

    async def client_exists(self, email: str) -> bool:
        """True if client still appears in central API or any inbound settings."""
        email = email.strip()
        if await self.find_client_records(email):
            return True

        try:
            inbounds = await self.list_inbounds()
        except XUIError:
            return False

        for ib in inbounds:
            try:
                obj = await self.get_inbound(ib.id)
            except XUIError:
                continue
            settings = _parse_json_field(obj.get("settings"))
            clients = settings.get("clients") if isinstance(settings, dict) else []
            if not isinstance(clients, list):
                continue
            for client in clients:
                if isinstance(client, dict) and self._match_client_email(
                    client.get("email") or "", email
                ):
                    return True
        return False

    @staticmethod
    def _bulk_delete_succeeded(bulk_result: dict, email: str) -> bool:
        """True when bulkDel confirms the client was removed or was already absent."""
        if not bulk_result:
            return False
        if int(bulk_result.get("deleted") or 0) > 0:
            return True
        for skip in bulk_result.get("skipped") or []:
            if not isinstance(skip, dict):
                continue
            if not XUIClient._match_client_email(skip.get("email", ""), email):
                continue
            reason = (skip.get("reason") or "").lower()
            if any(token in reason for token in ("not found", "no client", "does not exist")):
                return True
        return False

    async def _bulk_delete_clients(self, emails: list[str]) -> dict:
        """POST /panel/api/clients/bulkDel — preferred delete (no email-in-URL issues)."""
        unique = []
        seen: set[str] = set()
        for em in emails:
            key = (em or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(em.strip())
        if not unique:
            return {}
        data = await self._request(
            "POST",
            "/panel/api/clients/bulkDel",
            json={"emails": unique, "keepTraffic": False},
        )
        return data.get("obj") if isinstance(data.get("obj"), dict) else {}

    async def _remove_client_from_inbound(self, inbound_id: int, email: str) -> bool:
        """Remove client from inbound settings.clients[] (orphan / legacy cleanup)."""
        obj = await self.get_inbound(inbound_id)
        settings = _parse_json_field(obj.get("settings"))
        if not isinstance(settings, dict):
            settings = {}
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            return False
        new_clients = [
            c for c in clients
            if not (
                isinstance(c, dict)
                and self._match_client_email(c.get("email") or "", email)
            )
        ]
        if len(new_clients) == len(clients):
            return False
        settings = {**settings, "clients": new_clients}
        stream = _parse_json_field(obj.get("streamSettings"))
        if not isinstance(stream, dict):
            stream = {}
        await self.update_inbound(
            inbound_id, _inbound_update_payload(obj, settings, stream)
        )
        return True

    async def delete_client(self, email: str) -> None:
        """
        Delete from 3X-UI central clients DB + detach/scrub inbounds.
        Uses bulkDel first (reliable); verifies client is gone before returning.
        """
        email = email.strip()
        records = await self.find_client_records(email)
        inbound_ids: set[int] = set()
        for rec in records:
            for ib_id in rec.get("inboundIds") or []:
                try:
                    inbound_ids.add(int(ib_id))
                except (TypeError, ValueError):
                    pass

        if inbound_ids:
            try:
                await self.detach_client(email, list(inbound_ids))
            except XUIError as exc:
                logger.warning("detach before delete %s: %s", email, exc)

        bulk_result: dict = {}
        try:
            bulk_result = await self._bulk_delete_clients([email])
            deleted = int(bulk_result.get("deleted") or 0)
            skipped = bulk_result.get("skipped") or []
            if deleted:
                logger.info("bulkDel removed %s (deleted=%s)", email, deleted)
            elif skipped:
                logger.warning("bulkDel skipped %s: %s", email, skipped)
        except XUIError as exc:
            logger.warning("bulkDel failed for %s: %s", email, exc)

        try:
            await self._request(
                "POST",
                f"/panel/api/clients/del/{self._email_path(email)}",
                params={"keepTraffic": 0},
            )
            logger.info("Path delete API removed client: %s", email)
        except XUINotFound:
            logger.info("Path delete 404 for %s", email)
        except XUIAPIError as exc:
            logger.warning("Path delete API error for %s: %s", email, exc)

        scrub_ids: set[int] = set(inbound_ids)
        try:
            scrub_ids.update(ib.id for ib in await self.list_inbounds())
        except XUIError as exc:
            logger.warning("Could not list inbounds for delete scrub: %s", exc)

        for ib_id in scrub_ids:
            try:
                if await self._remove_client_from_inbound(ib_id, email):
                    logger.info("Scrubbed %s from inbound %s settings", email, ib_id)
            except XUIError as exc:
                logger.warning("Inbound scrub failed for %s on %s: %s", email, ib_id, exc)

        # Central clients API is the source of truth for the panel UI. List/paged
        # endpoints and inbound settings JSON can lag or keep ghost rows after bulkDel.
        bulk_ok = self._bulk_delete_succeeded(bulk_result, email)
        try:
            await self.get_client(email)
        except XUINotFound:
            logger.info("Client fully removed from panel: %s", email)
            return
        except XUIError as exc:
            if bulk_ok:
                logger.warning(
                    "Post-delete get_client failed for %s after bulkDel: %s — treating as deleted",
                    email,
                    exc,
                )
                return
            raise

        raise XUIAPIError(
            f"Panel client {email} still exists after delete (bulkDel={bulk_result})"
        )

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
        if not inbound_ids:
            return
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
