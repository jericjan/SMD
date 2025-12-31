from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from main import VERSION
from smd.strings import LINUX_RELEASE_PREFIX, WINDOWS_RELEASE_PREFIX


def archive():
    main_folder = Path.cwd() / "dist/main"
    prefix = 'unsupported'
    if sys.platform == "win32":
        prefix = WINDOWS_RELEASE_PREFIX
    elif sys.platform == "linux":
        prefix = LINUX_RELEASE_PREFIX
    zip_file = main_folder.parent / f"{prefix}_SMD_{VERSION}.zip"

    if zip_file.exists():
        zip_file.unlink()

    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        files = list(main_folder.rglob("*"))
        count = len(files)
        for idx, file in enumerate(files):
            print(f"{idx+1} / {count}")
            zf.write(file, file.relative_to(main_folder))
