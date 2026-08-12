from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from colorama import Fore, Style

from smd.prompts import prompt_text
from smd.steam_client import SteamInfoProvider
from smd.utils import enter_path


@dataclass
class ManifestContext:
    app_id: int
    "The base app ID"
    app_data: dict[str, Any]
    "get_product_info data for app id, via SteamInfoProvider.get_single_app_info"
    provider: SteamInfoProvider
    auto: bool = True
    "whether the user chose to automatically get IDs or not"
    _dlc_data: dict[int, Any] | None = None
    "Lazy-loaded DLC data"

    @property
    def dlc_data(self) -> dict[int, Any]:
        """Lazy loads all DLC info for the game"""
        if self._dlc_data is None:
            self._dlc_data = self.provider.expand_dlc(self.app_data)
        return self._dlc_data


class IManifestStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Clean name of the strategy"""

    @abstractmethod
    def get_manifest_id(self, ctx: ManifestContext, depot_id: str) -> str | None:
        pass


class StandardManifestStrategy(IManifestStrategy):
    """Just get the manifest directly from initial request"""

    @property
    def name(self):
        return "Direct"

    def get_manifest_id(
        self, ctx: ManifestContext, depot_id: str | int
    ) -> str | None:
        return enter_path(
            ctx.app_data, "depots", str(depot_id), "manifests", "public"
        ).get("gid")


class SharedDepotManifestStrategy(IManifestStrategy):
    """Usually stuff like vcredist"""

    @property
    def name(self):
        return "Shared Install"

    def get_manifest_id(
        self, ctx: ManifestContext, depot_id: str | int
    ) -> str | None:
        target_app_id = enter_path(ctx.app_data, "depots", str(depot_id)).get(
            "depotfromapp"
        )

        if not target_app_id:
            return None

        target_data = ctx.provider.get_single_app_info(int(target_app_id))

        return enter_path(
            target_data, "depots", str(depot_id), "manifests", "public"
        ).get("gid")


class InnerDepotManifestStrategy(IManifestStrategy):
    """Inner depot DLC"""

    @property
    def name(self):
        return "Inner Depot From DLC"

    def get_manifest_id(self, ctx: ManifestContext, depot_id: str) -> str | None:
        for dlc_data in ctx.dlc_data.values():
            depots = dlc_data.get("depots", {})
            if depot_id in depots:
                return enter_path(depots[depot_id], "manifests", "public").get("gid")
        return None


class ManualManifestStrategy(IManifestStrategy):
    @property
    def name(self):
        return "Manual"

    def get_manifest_id(self, ctx: ManifestContext, depot_id: str) -> str | None:
        if ctx.app_id == int(depot_id):
            print(
                Fore.YELLOW
                + "The base app ID had a decryption key, and manifest ID could not be"
                " found. Skipping..."
                + Style.RESET_ALL
            )
            return ""
        if ctx.auto:
            print(
                "All auto methods failed. Type the manifest ID manually here, "
                f"enter a blank to skip downloading it.\nYou can find the ID here: https://steamdb.info/depot/{depot_id}/manifests/"
            )
        return prompt_text(f"Depot {depot_id}: ").strip()


class ManifestIDResolver:
    def __init__(self, strategies: list[IManifestStrategy]):
        self.strategies = strategies

    def resolve(self, ctx: ManifestContext, depot_id: str) -> tuple[str, str]:
        """Iterates strategies until a manifest is found.
        Returns manifest and strategy name"""
        for strategy in self.strategies:
            manifest = strategy.get_manifest_id(ctx, depot_id)
            if manifest is not None:
                return manifest, strategy.name

        raise Exception(f"Unable to resolve manifest for depot {depot_id}")
