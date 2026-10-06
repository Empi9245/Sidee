"""Build a source ZIP that opens with start-windows.bat on a fresh Windows PC."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
TOP_LEVEL = ("README.md", "LICENSE", "requirements.txt", "sidee.py",
             "start-windows.bat", "start-windows.ps1")
ASSETS = ("sidee-logo.png", "nuvio-wordmark.png", "jellyfin.png")


def build(destination=None):
    destination = Path(destination or ROOT / "dist" / "sidee-windows.zip")
    files = [ROOT / name for name in TOP_LEVEL]
    files += sorted((ROOT / "core").glob("*.py"))
    files += [ROOT / "core" / "dashboard.html", ROOT / "core" / "tv-client.bundle"]
    files += [ROOT / "assets" / name for name in ASSETS]
    for source in files:
        if not source.is_file():
            raise FileNotFoundError(f"Release file is missing: {source.relative_to(ROOT)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, "Sidee/" + source.relative_to(ROOT).as_posix())
    return destination


if __name__ == "__main__":
    print(build())
