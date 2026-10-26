"""Manifest request code providers."""

import asyncio
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable

from smd.http_utils import get_base_domain, get_request
from smd.prompts import prompt_text
from smd.secret_store import b64_decrypt

if sys.platform == "win32":
    import msvcrt
else:

    class msvcrt:
        @staticmethod
        def kbhit():
            return False

        @staticmethod
        def getch():
            return None


async def _wait_for_enter():
    print(
        "If it takes too long, press Enter to cancel the request "
        "and input manually..."
    )
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return
        await asyncio.sleep(0.05)


class IMRCStrategy(ABC):
    """Source used to obtain a manifest request code."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name used to select this strategy."""

    async def get_gmrc(self, manifest_id: str | int) -> str | None:
        """Get a manifest request code with shared cancellation handling."""
        print("Getting request code...")

        if sys.platform != "win32":
            return await self._request(manifest_id)

        request_task = asyncio.create_task(self._request(manifest_id))
        cancel_task = asyncio.create_task(_wait_for_enter())

        done, pending = await asyncio.wait(
            {request_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED
        )

        result = None
        if request_task in done:
            result = request_task.result()

        if cancel_task in done and not request_task.done():
            print("Cancelling request...", end="")
            request_task.cancel()

        for task in pending:
            task.cancel()

        try:
            if result is None:
                result = await request_task
        except asyncio.CancelledError:
            print("✅")
            result = prompt_text("Please provide the manifest request code:")

        return result

    @abstractmethod
    async def _request(self, manifest_id: str | int) -> str | None:
        """Make the strategy-specific network request."""


class WudrmMRCStrategy(IMRCStrategy):
    """Get MRC from wudrm endpoint."""

    @property
    def name(self) -> str:
        return "wudrm"

    async def _request(self, manifest_id: str | int) -> str | None:
        # Yes, I'm aware it's not actually "encrypted" since I included the password.
        template_url = b64_decrypt(
            b"gzTYiUdY7dR2oFPM+cUEUpSnLYn17uq09F8PATpFKT8=",
            b"rok2PaPQ2T0CF3RZXe+AfytF7i+Yo/kEykq4hnPSSrhRDeESOARdQD4+SzqZqeG5C5U4fAiuEUuPpr1CaXl9V/Xv9EcZdWk1BbyUqCXP8FHkqdGm",
        )
        url = template_url.format(manifest_id=manifest_id)
        headers = {"Referer": get_base_domain(url)}
        return await get_request(url, headers=headers, print_on_err=False)


class ManifestDexMRCStrategy(IMRCStrategy):
    """Get MRC from ManifestDeX."""

    @property
    def name(self) -> str:
        return "manifest_dex"

    async def _request(self, manifest_id: str | int) -> str | None:
        url = f"https://manifest.manifestdex.com/{manifest_id}"
        headers = {"User-Agent": "ManifestDeX/1.0"}
        return await get_request(url, headers=headers, print_on_err=False)


class MRCResolver:
    """Try MRC strategies in the configured order."""

    def __init__(self, strategies: Iterable[IMRCStrategy] | None = None):
        configured_strategies = (
            strategies
            if strategies is not None
            else (WudrmMRCStrategy(), ManifestDexMRCStrategy())
        )
        self.strategies = tuple(configured_strategies)

    async def resolve(self, manifest_id: str | int) -> str | None:
        for strategy in self.strategies:
            print(f"Trying {strategy.name}...")
            result = await strategy.get_gmrc(manifest_id)
            if result is not None:
                return result
            print(f"{strategy.name} failed.")
        return None


_resolver = MRCResolver()


async def get_gmrc(manifest_id: str | int) -> str | None:
    """Get a manifest request code, trying WUDRM and then ManifestDeX."""
    return await _resolver.resolve(manifest_id)
