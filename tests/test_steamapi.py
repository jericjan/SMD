import json

from smd.steam_client import SteamInfoProvider


def test_steam():
    prov = SteamInfoProvider()
    a = prov.get_single_app_info(4435340)
    print(json.dumps(a))