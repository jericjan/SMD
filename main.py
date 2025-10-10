import io
from typing import Union
import zipfile
from urllib.parse import urljoin

import requests

from decrypt_manifest import decrypt_manifest


def request_code(manifest_id: Union[str, int]):
    # The URL we want to make a GET request to.
    url = f"http://gmrc.openst.top/manifest/{manifest_id}"

    try:
        # Make the GET request.
        response = requests.get(url)

        # Check if the request was successful (status code 200).
        if response.status_code == 200:
            print("✅ Request was successful!")
            print(f"Status Code: {response.status_code}")

            # The response from this API is in JSON format.
            # We can easily convert it to a Python dictionary.
            return response.text

        else:
            # If the request was not successful, print the error status code.
            print(f"❌ Request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception("openst failed lmao")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


def main():
    depot_id = 2475491
    manifest_id = 2537253174922439408
    dec_key = "397ceaf971a43c7d35d5eade1443d05df02019c433895547be26e88b177d948d"

    print("Getting request code...")
    req_code = request_code(manifest_id)
    print(f"Request code is: {req_code}")

    cdn = "https://cache1-man-rise.steamcontent.com/"  # You can get cdn urls by running download_sources in steam console
    manifest_url = urljoin(cdn, f"depot/{depot_id}/manifest/{manifest_id}/5/{req_code}")

    r = requests.get(manifest_url)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(".")

    decrypt_manifest("z", f"{depot_id}_{manifest_id}.manifest", dec_key)


if __name__ == "__main__":
    main()