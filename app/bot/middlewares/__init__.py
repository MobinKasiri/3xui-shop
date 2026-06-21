from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import async_sessionmaker

from .channel_gate import ChannelGateMiddleware
from .database import DBSessionMiddleware
from .maintenance_gate import MaintenanceMiddleware
from .throttling import ThrottlingMiddleware
from .vpn_service import VPNServiceMiddleware


def register(dispatcher: Dispatcher, session: async_sessionmaker) -> None:
    for mw in [
        ThrottlingMiddleware(),
        MaintenanceMiddleware(),
        DBSessionMiddleware(session),
        ChannelGateMiddleware(),
        VPNServiceMiddleware(),
    ]:
        dispatcher.update.middleware.register(mw)
