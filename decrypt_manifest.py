import base64
import io
import struct
import zipfile
import zlib
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from content_manifest_pb2 import (ContentManifestMetadata,
                                  ContentManifestPayload)

# Magic numbers
PROTOBUF_PAYLOAD_MAGIC = 0x71F617D0
PROTOBUF_METADATA_MAGIC = 0x1F4812BE
PROTOBUF_SIGNATURE_MAGIC = 0x1B81B817
PROTOBUF_ENDOFMANIFEST_MAGIC = 0x32C415AB


def decrypt_filename(b64_encrypted_name: str, key_bytes: bytes):
    """Decrypts a single filename using the SteamKit AES-ECB/CBC method."""
    try:
        decoded_data = base64.b64decode(b64_encrypted_name)

        # The first 16 bytes are an encrypted IV. Decrypt it with ECB to get the real IV.
        cipher_ecb = AES.new(key_bytes, AES.MODE_ECB)  # type: ignore
        iv = cipher_ecb.decrypt(decoded_data[:16])

        # The rest of the data is the actual ciphertext.
        ciphertext = decoded_data[16:]

        # Decrypt the ciphertext using the real IV and CBC mode.
        cipher_cbc = AES.new(key_bytes, AES.MODE_CBC, iv)  # type: ignore
        decrypted_padded = cipher_cbc.decrypt(ciphertext)

        # Unpad and clean up the result.
        unpadded = unpad(decrypted_padded, AES.block_size)
        return unpadded.rstrip(b'\x00').decode('utf-8')
    except Exception:
        # If decryption fails for any reason, return the original string
        return b64_encrypted_name


def decrypt_manifest(encrypted_file: io.BytesIO, output_filepath: Path, dec_key: str):

    data = encrypted_file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            data = zf.read(zf.filelist[0].filename)
    except zipfile.BadZipFile:
        pass

    stream = io.BytesIO(data)

    magic, payload_length = struct.unpack('<II', stream.read(8))
    if magic != PROTOBUF_PAYLOAD_MAGIC:
        raise ValueError("Bad payload magic")
    payload_bytes = stream.read(payload_length)

    magic, metadata_length = struct.unpack('<II', stream.read(8))
    if magic != PROTOBUF_METADATA_MAGIC:
        raise ValueError("Bad metadata magic")
    metadata_bytes = stream.read(metadata_length)

    original_payload = ContentManifestPayload()
    original_payload.ParseFromString(payload_bytes)

    # --- PROCESSING LOGIC ---
    print(f"\nFound {len(original_payload.mappings)} file mappings. Processing...")

    # 1. Decrypt filenames
    key_bytes = bytes.fromhex(dec_key)
    new_mappings: list[ContentManifestPayload.FileMapping] = []
    for mapping in original_payload.mappings:
        new_mapping = ContentManifestPayload.FileMapping()
        new_mapping.CopyFrom(mapping)  # Copy all original data (size, flags, chunks, etc.)

        # Decrypt filename and linktarget if they exist
        new_mapping.filename = decrypt_filename(mapping.filename, key_bytes)
        if mapping.linktarget:
            new_mapping.linktarget = decrypt_filename(mapping.linktarget, key_bytes)

        new_mappings.append(new_mapping)
    print("✅ Decrypted all filenames.")

    # 3. Create the new payload object with the sorted, decrypted data
    fixed_payload = ContentManifestPayload()
    fixed_payload.mappings.extend(new_mappings)

    # 4. Serialize the new payload and recalculate crc_clear
    fixed_payload_bytes = fixed_payload.SerializeToString()
    length_bytes = struct.pack('<I', len(fixed_payload_bytes))
    data_to_checksum = length_bytes + fixed_payload_bytes
    new_crc = zlib.crc32(data_to_checksum) & 0xFFFFFFFF
    print(f"✅ Recalculated crc_clear: {new_crc}")

    # 5. Update and re-serialize the metadata
    metadata = ContentManifestMetadata()
    metadata.ParseFromString(metadata_bytes)
    metadata.crc_clear = new_crc
    metadata.filenames_encrypted = False  # Mark the filenames as decrypted
    fixed_metadata_bytes = metadata.SerializeToString()

    # 6. Write the new manifest file
    print(f"\n--- Writing new manifest to '{output_filepath}' ---")
    with open(output_filepath, 'wb') as f:
        f.write(struct.pack('<II', PROTOBUF_PAYLOAD_MAGIC, len(fixed_payload_bytes)))
        f.write(fixed_payload_bytes)

        f.write(struct.pack('<II', PROTOBUF_METADATA_MAGIC, len(fixed_metadata_bytes)))
        f.write(fixed_metadata_bytes)

        f.write(struct.pack('<II', PROTOBUF_SIGNATURE_MAGIC, 0))
        f.write(struct.pack('<I', PROTOBUF_ENDOFMANIFEST_MAGIC))

    print("✅ Done.")
