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
    file_type = ''
    if sys.platform == "win32":
        prefix = WINDOWS_RELEASE_PREFIX
        file_type = ".zip"
    elif sys.platform == "linux":
        prefix = LINUX_RELEASE_PREFIX
        file_type = ".tar.xz"
    zip_file = main_folder.parent / f"{prefix}_SMD_{VERSION}{file_type}"

    if zip_file.exists():
        zip_file.unlink()

    if sys.platform == "win32":
        with zipfile.ZipFile(
            zip_file, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            files = list(main_folder.rglob("*"))
            count = len(files)
            for idx, file in enumerate(files):
                print(f"{idx+1} / {count}")
                zf.write(file, file.relative_to(main_folder))
    elif sys.platform == "linux":
        tar = shutil.which("tar")
        if not tar:
            print("tar not found. can't archive build into tar.xz file.")
        subprocess.run([tar, "-cJvf", str(zip_file.resolve()), "-C", main_folder, "."])

if __name__ == "__main__":
    archive()