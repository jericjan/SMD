import pytest

from smd.manifest.crypto import view_manifest
from smd.manifest.downloader import ManifestDownloader
from smd.steam_client import SteamInfoProvider
from smd.steam_path import init_steam_path
from smd.utils import get_os_type
from smd.zip import read_nth_file_from_zip_bytes


@pytest.mark.parametrize("depot_id,manifest_id", [(3711591, 3918452883057196630)])
def test_dl_and_view_manifest(depot_id: int, manifest_id: int):

    os_type = get_os_type()
    provider = SteamInfoProvider()
    steam_path = init_steam_path(os_type)

    d = ManifestDownloader(provider, steam_path)
    zip_file, _is_zipped = d.download_single_manifest(str(depot_id), str(manifest_id))
    if zip_file is None:
        assert False, "Could not DL manifest"
    raw_b = read_nth_file_from_zip_bytes(0, zip_file)
    if raw_b is None:
        assert False, "Could not extract ZIP"
    view_manifest(raw_b.read())