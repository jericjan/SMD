import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

import gevent
from steam.client import SteamClient  # type: ignore
from steam.core.msg import MsgProto  # type: ignore
from steam.protobufs.steammessages_publishedfile_pb2 import (
    CPublishedFile_GetDetails_Response,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkshopItemContext:
    client: SteamClient
    workshop_id: int
    "AKA PublishedFileId"


class IUgcIdStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Clean name of the strategy"""
        pass

    @abstractmethod
    def get_ugc_id(self, ctx: WorkshopItemContext) -> Optional[int]:
        pass


class StandardUgcIdStrategy(IUgcIdStrategy):

    @property
    def name(self):
        return "Standard"

    def _send_request(self, client: SteamClient, workshop_id: int):
        resp: Any = (  # pyright: ignore[reportUnknownVariableType]
            client.send_um_and_wait(  # pyright: ignore[reportUnknownMemberType]
                "PublishedFile.GetDetails#1",
                {
                    "publishedfileids": [workshop_id],
                    "includetags": False,
                    "includeadditionalpreviews": False,
                    "includechildren": False,
                    "includekvtags": False,
                    "includevotes": False,
                    "short_description": True,
                    "includeforsaledata": False,
                    "includemetadata": False,
                    "language": 0,
                },
                timeout=7,
            )
        )
        if (
            not isinstance(resp, MsgProto)
            or resp.body is None  # pyright: ignore[reportUnknownMemberType]
        ):
            return None
        if not isinstance(
            resp.body,  # pyright: ignore[reportUnknownMemberType]
            CPublishedFile_GetDetails_Response,
        ):
            return None
        details = resp.body.publishedfiledetails
        return details[0]

    def _get_workshop_items_details(self, ctx: WorkshopItemContext):
        if not ctx.client.logged_on:
            print("Logging in anonymously...", end="", flush=True)
            ctx.client.anonymous_login()
            print(" Done!")
        while True:
            try:
                resp = self._send_request(ctx.client, ctx.workshop_id)
                return resp
            except gevent.Timeout:
                print("Request timed out. Trying again")
                try:
                    ctx.client.anonymous_login()  # might fix the endless timeout loop
                except RuntimeError:  # Alr logged in error
                    pass
                continue
            break

    def get_ugc_id(self, ctx: WorkshopItemContext) -> Optional[int]:
        details = self._get_workshop_items_details(ctx)
        if details:
            return details.hcontent_file


class UgcIDResolver:
    def __init__(self, strategies: List[IUgcIdStrategy]):
        self.strategies = strategies

    def resolve(self, ctx: WorkshopItemContext) -> tuple[int, str]:
        """Iterates strategies until a UGC ID is found.
        Returns UGC ID and strategy name"""
        for strategy in self.strategies:
            manifest = strategy.get_ugc_id(ctx)
            if manifest is not None:
                return manifest, strategy.name

        raise Exception(f"Unable to resolve manifest for depot {ctx.workshop_id}")
