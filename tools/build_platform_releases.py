"""Build the public source package under each platform download name."""
from pathlib import Path
import hashlib

if __package__:
    from .build_windows_release import ROOT, build
else:
    from build_windows_release import ROOT, build

PLATFORMS = ("windows", "macos", "linux", "android")


def build_all():
    return {platform: build(ROOT / "dist" / f"sidee-{platform}.zip")
            for platform in PLATFORMS}


def write_checksums(archives, destination=None):
    """Write the SHA-256 manifest served next to the public downloads."""
    destination = Path(destination or ROOT / "dist" / "SHA256SUMS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for archive in archives.values():
        data = Path(archive).read_bytes()
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {Path(archive).name}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


if __name__ == "__main__":
    archives = build_all()
    for platform, archive in archives.items():
        print(f"{platform}: {archive}")
    print(f"checksums: {write_checksums(archives)}")
