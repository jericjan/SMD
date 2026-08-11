import zipfile
from io import BytesIO
from pathlib import Path
from typing import Literal, overload

from colorama import Fore, Style


@overload
def read_lua_from_zip(path: Path | BytesIO) -> str | None: ...


@overload
def read_lua_from_zip(
    path: Path | BytesIO, decode: Literal[True]
) -> str | None: ...


@overload
def read_lua_from_zip(
    path: Path | BytesIO, decode: Literal[False]
) -> bytes | None: ...


def read_lua_from_zip(path: Path | BytesIO, decode: bool = True):
    """Given a zip path, return the string contents,
    None if it can't be found"""
    lua_contents = None
    try:
        with zipfile.ZipFile(path) as f:
            for file in f.filelist:
                if file.filename.endswith(".lua"):
                    print(f".lua found in ZIP: {file.filename}")
                    if lua_contents is None:
                        lua_contents = f.read(file)
                elif file.filename.endswith(".manifest"):
                    filename = Path(file.filename).name
                    print(f"Manifest found in ZIP: {filename}")
                    manifests_dir = Path.cwd() / "manifests"
                    manifests_dir.mkdir(exist_ok=True)
                    with (manifests_dir / filename).open("wb") as mf:
                        mf.write(f.read(file))
            if lua_contents is None:
                print(Fore.RED + "Could not find the lua in the ZIP" + Style.RESET_ALL)
    except zipfile.BadZipFile:
        return
    if decode and lua_contents:
        lua_contents = lua_contents.decode(encoding="utf-8")
    return lua_contents


def read_file_from_zip_bytes(filename: str | zipfile.ZipInfo, bytes: bytes):
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


def zip_folder(folder_path: Path, output_path: Path):
    """ZIPs to a BytesIO then to the actual file to prevent infinite recursion"""
    tmp = BytesIO()
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in folder_path.rglob('*'):
            if file.is_file():
                zipf.write(file, arcname=file.relative_to(folder_path))
    tmp.seek(0)
    with output_path.open("wb") as f:
        f.write(tmp.read())

class BytesIOZip:
    """Used for creating a ZIP file that exists in a BytesIO object"""
    def __init__(self):
        self.file = BytesIO()
        self.to_be_added: list[tuple[str | Path | bytes, str]] = []
        """List of (Path to local file / raw contents, path inside ZIP)"""

    def prepare_local_file(self, paths: Path | list[Path]):
        """Adds a local existing file to the ZIP"""
        if isinstance(paths, Path):
            paths = [paths]
        self.to_be_added.extend([(x, x.name) for x in paths])

    def prepare_str_file(self, name: str, contents: str | bytes):
        """Adds an in-memory file to the ZIP

        Args:
            name (str): Name of your file in the ZIP
            contents (str | bytes): The contents of that file
        """
        self.to_be_added.append((contents, name))

    def write(self):
        "Writes all the prepared files to the ZIP"
        with zipfile.ZipFile(self.file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file, arcname in self.to_be_added:
                if isinstance(file, Path):
                    if file.is_file():
                        zipf.write(file, arcname=arcname)
                else:
                    zipf.writestr(arcname, file)
        self.file.seek(0)
        return self.file

    def save_to_file(self, out: Path):
        """Saves the ZIP to a local file. For testing."""
        self.file.seek(0)
        out.write_bytes(self.file.getvalue())
