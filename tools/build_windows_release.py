"""Build a source ZIP that opens with start-windows.bat on a fresh Windows PC."""
from pathlib import Path
import os
import tempfile
import zipfile

if __package__:
    from .public_release_guard import ASSETS, TOP_LEVEL, PUBLIC_FILES, check_public_source, check_zip
else:
    from public_release_guard import ASSETS, TOP_LEVEL, PUBLIC_FILES, check_public_source, check_zip

ROOT = Path(__file__).resolve().parent.parent


def build(destination=None):
    destination = Path(destination or ROOT / "dist" / "sidee-windows.zip")
    check_public_source(ROOT)
    files = [ROOT / name for name in PUBLIC_FILES]
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".sidee-release-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in files:
                archive.write(source, "Sidee/" + source.relative_to(ROOT).as_posix())
        check_zip(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__ == "__main__":
    print(build())
