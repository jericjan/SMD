from io import BytesIO
from typing import Literal, Union, overload
import zipfile
from pathlib import Path


@overload
def read_lua_from_zip(path: Union[Path, BytesIO]) -> Union[str, None]: ...


@overload
def read_lua_from_zip(
    path: Union[Path, BytesIO], decode: Literal[True]
) -> Union[str, None]: ...


@overload
def read_lua_from_zip(
    path: Union[Path, BytesIO], decode: Literal[False]
) -> Union[bytes, None]: ...


def read_lua_from_zip(path: Union[Path, BytesIO], decode: bool = True):
    """Given a zip path, return the string contents,
    None if it can't be found"""
    lua_contents = None
    try:
        with zipfile.ZipFile(path) as f:
            for file in f.filelist:
                if file.filename.endswith(".lua"):
                    print(f".lua found in ZIP: {file.filename}")
                    lua_contents = f.read(file)
                    break  # lua found in ZIP, stop searching
            else:
                print("Could not find the lua in the ZIP")
    except zipfile.BadZipFile:
        return
    if decode and lua_contents:
        lua_contents = lua_contents.decode(encoding="utf-8")
    return lua_contents


def read_file_from_zip_bytes(filename: Union[str, zipfile.ZipInfo], bytes: bytes):
    """Returns none if it's an invalid ZIP file"""
    try:
        with zipfile.ZipFile(BytesIO(bytes)) as f:
            return BytesIO(f.read(filename))
    except zipfile.BadZipFile:
        return


def read_nth_file_from_zip_bytes(nth: int, bytes: bytes):
    """Returns none if it's an invalid ZIP file"""
    try:
        with zipfile.ZipFile(BytesIO(bytes)) as f:
            return BytesIO(f.read(f.filelist[nth].filename))
    except zipfile.BadZipFile:
        return
