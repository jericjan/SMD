from steam.client import SteamClient
from steam.client.cdn import CDNClient
from steam.enums.emsg import EMsg
import requests

def request_code(manifest_id):
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
        


client = SteamClient()
cdn = CDNClient(client)

client.cli_login()

app_id = 2653790
depot_id = 2653791
manifest_id = 	4401022976514973949
dec_key = "057987e441949d496886cc38feefea453a2863c2ee7f4afbf010230d6bd89372".encode()

#a = cdn.get_depot_key(app_id, depot_id)
#print(a)

# req_code = cdn.get_manifest_request_code(app_id, depot_id, manifest_id)
req_code = request_code(4401022976514973949)
print(f"req code is: {req_code}")

print("Getting manifest....................")
manifest = cdn.get_manifest(app_id, depot_id, manifest_id, False, req_code)
print("Decrypting filenames....................")
manifest.decrypt_filenames(dec_key)
print("Saving to file....................")
with open(f"{depot_id}_{manifest_id}.manifest", "wb") as f:
    f.write(manifest.serialize(False))

client.logout()