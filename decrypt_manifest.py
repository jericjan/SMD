import base64
import io
import struct
import zipfile
import zlib

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database

_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor.FileDescriptor(name='content_manifest.proto', package='', syntax='proto2', serialized_options=b'H\001\220\001\000', serialized_pb=b'\n\x16\x63ontent_manifest.proto\"\xef\x02\n\x16\x43ontentManifestPayload\x12\x35\n\x08mappings\x18\x01 \x03(\x0b\x32#.ContentManifestPayload.FileMapping\x1a\x9d\x02\n\x0b\x46ileMapping\x12\x10\n\x08\x66ilename\x18\x01 \x01(\t\x12\x0c\n\x04size\x18\x02 \x01(\x04\x12\r\n\x05\x66lags\x18\x03 \x01(\r\x12\x14\n\x0csha_filename\x18\x04 \x01(\x0c\x12\x13\n\x0bsha_content\x18\x05 \x01(\x0c\x12=\n\x06\x63hunks\x18\x06 \x03(\x0b\x32-.ContentManifestPayload.FileMapping.ChunkData\x12\x12\n\nlinktarget\x18\x07 \x01(\t\x1a\x61\n\tChunkData\x12\x0b\n\x03sha\x18\x01 \x01(\x0c\x12\x0b\n\x03\x63rc\x18\x02 \x01(\x07\x12\x0e\n\x06offset\x18\x03 \x01(\x04\x12\x13\n\x0b\x63\x62_original\x18\x04 \x01(\r\x12\x15\n\rcb_compressed\x18\x05 \x01(\r\"\xec\x01\n\x17\x43ontentManifestMetadata\x12\x10\n\x08\x64\x65pot_id\x18\x01 \x01(\r\x12\x14\n\x0cgid_manifest\x18\x02 \x01(\x04\x12\x15\n\rcreation_time\x18\x03 \x01(\r\x12\x1b\n\x13\x66ilenames_encrypted\x18\x04 \x01(\x08\x12\x18\n\x10\x63\x62_disk_original\x18\x05 \x01(\x04\x12\x1a\n\x12\x63\x62_disk_compressed\x18\x06 \x01(\x04\x12\x15\n\runique_chunks\x18\x07 \x01(\r\x12\x15\n\rcrc_encrypted\x18\x08 \x01(\r\x12\x11\n\tcrc_clear\x18\t \x01(\r\"-\n\x18\x43ontentManifestSignature\x12\x11\n\tsignature\x18\x01 \x01(\x0c')
ContentManifestPayload = _reflection.GeneratedProtocolMessageType('ContentManifestPayload', (_message.Message,), {'FileMapping': _reflection.GeneratedProtocolMessageType('FileMapping', (_message.Message,), {'ChunkData': _reflection.GeneratedProtocolMessageType('ChunkData', (_message.Message,), {'DESCRIPTOR': DESCRIPTOR.message_types_by_name['ContentManifestPayload'].nested_types[0].nested_types[0]}), 'DESCRIPTOR': DESCRIPTOR.message_types_by_name['ContentManifestPayload'].nested_types[0]}), 'DESCRIPTOR': DESCRIPTOR.message_types_by_name['ContentManifestPayload']})
ContentManifestMetadata = _reflection.GeneratedProtocolMessageType('ContentManifestMetadata', (_message.Message,), {'DESCRIPTOR': DESCRIPTOR.message_types_by_name['ContentManifestMetadata']})
_sym_db.RegisterMessage(ContentManifestPayload); _sym_db.RegisterMessage(ContentManifestPayload.FileMapping); _sym_db.RegisterMessage(ContentManifestPayload.FileMapping.ChunkData); _sym_db.RegisterMessage(ContentManifestMetadata)

# --- CONFIGURATION ---
PROTOBUF_PAYLOAD_MAGIC = 0x71F617D0
PROTOBUF_METADATA_MAGIC = 0x1F4812BE
PROTOBUF_SIGNATURE_MAGIC = 0x1B81B817
PROTOBUF_ENDOFMANIFEST_MAGIC = 0x32C415AB

def decrypt_filename(b64_encrypted_name, key_bytes):
    """Decrypts a single filename using the SteamKit AES-ECB/CBC method."""
    try:
        decoded_data = base64.b64decode(b64_encrypted_name)
        
        # The first 16 bytes are an encrypted IV. Decrypt it with ECB to get the real IV.
        cipher_ecb = AES.new(key_bytes, AES.MODE_ECB)
        iv = cipher_ecb.decrypt(decoded_data[:16])
        
        # The rest of the data is the actual ciphertext.
        ciphertext = decoded_data[16:]
        
        # Decrypt the ciphertext using the real IV and CBC mode.
        cipher_cbc = AES.new(key_bytes, AES.MODE_CBC, iv)
        decrypted_padded = cipher_cbc.decrypt(ciphertext)
        
        # Unpad and clean up the result.
        unpadded = unpad(decrypted_padded, AES.block_size)
        return unpadded.rstrip(b'\x00').decode('utf-8')
    except Exception:
        # If decryption fails for any reason, return the original string
        return b64_encrypted_name

def decrypt_manifest(input_filepath, output_filepath, dec_key):
    print(f"--- Reading and parsing '{input_filepath}' ---")
    
    with open(input_filepath, 'rb') as f: data = f.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf: data = zf.read(zf.filelist[0].filename)
    except zipfile.BadZipFile: pass
    
    stream = io.BytesIO(data)
    
    magic, payload_length = struct.unpack('<II', stream.read(8))
    if magic != PROTOBUF_PAYLOAD_MAGIC: raise ValueError("Bad payload magic")
    payload_bytes = stream.read(payload_length)

    magic, metadata_length = struct.unpack('<II', stream.read(8))
    if magic != PROTOBUF_METADATA_MAGIC: raise ValueError("Bad metadata magic")
    metadata_bytes = stream.read(metadata_length)

    original_payload = ContentManifestPayload()
    original_payload.ParseFromString(payload_bytes)
    
    # --- PROCESSING LOGIC ---
    print(f"\nFound {len(original_payload.mappings)} file mappings. Processing...")
    
    # 1. Decrypt filenames
    key_bytes = bytes.fromhex(dec_key)
    new_mappings = []
    for mapping in original_payload.mappings:
        new_mapping = ContentManifestPayload.FileMapping()
        new_mapping.CopyFrom(mapping) # Copy all original data (size, flags, chunks, etc.)
        
        # Decrypt filename and linktarget if they exist
        new_mapping.filename = decrypt_filename(mapping.filename, key_bytes)
        if mapping.linktarget:
            new_mapping.linktarget = decrypt_filename(mapping.linktarget, key_bytes)
            
        new_mappings.append(new_mapping)
    print("✅ Decrypted all filenames.")

    # 2. Sort the new list of mappings by filename (case-insensitive)
    new_mappings.sort(key=lambda m: m.filename.lower())
    print("✅ Sorted all file mappings alphabetically.")

    # 3. Create the new payload object with the sorted, decrypted data
    #    Chunk order is preserved because we copied it directly.
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
    metadata.filenames_encrypted = False # Mark the filenames as decrypted
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
