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
EXECUTABLES = {"start-unix.sh", "start-macos.command", "start-linux.sh",
               "start-android.sh"}


# Fixed timestamp so a build from a clean checkout is byte-identical: the ZIP
# depends only on the reviewed file contents and their order, never on the
# checkout time or the machine that built it.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


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
                name = "Sidee/" + source.relative_to(ROOT).as_posix()
                info = zipfile.ZipInfo(name, FIXED_TIME)
                info.create_system = 3
                info.external_attr = ((0o100755 if source.name in EXECUTABLES else 0o100644) << 16)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, source.read_bytes())
        check_zip(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__ == "__main__":
    print(build())
