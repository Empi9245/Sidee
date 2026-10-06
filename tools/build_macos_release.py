"""Build and verify a self-contained macOS app and drag-to-Applications DMG."""
import argparse
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}
RESOURCES = (
    "core/dashboard.html", "core/tv-client.bundle",
    "assets/sidee-logo.png", "assets/nuvio-wordmark.png", "assets/jellyfin.png",
    "README.md", "LICENSE",
)


def run(*arguments, **kwargs):
    return subprocess.run([str(value) for value in arguments], check=True, **kwargs)


def normalized_architecture(value):
    aliases = {"arm64": "arm64", "aarch64": "arm64", "x64": "x64",
               "x86_64": "x64", "amd64": "x64"}
    try:
        return aliases[value.lower()]
    except KeyError:
        raise ValueError(f"Unsupported macOS architecture: {value}") from None


def validate_version(value):
    value = value.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("The bundle version must use X.Y.Z (optionally prefixed with v).")
    return value


def make_icon():
    """Convert the existing app logo with macOS's built-in image tools."""
    icon_root = ROOT / "build" / "macos"
    iconset = icon_root / "Sidee.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    source = ROOT / "assets" / "sidee-logo.png"
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = "@2x" if scale == 2 else ""
            destination = iconset / f"icon_{size}x{size}{suffix}.png"
            run("sips", "-z", size * scale, size * scale, source, "--out", destination,
                stdout=subprocess.DEVNULL)
    destination = icon_root / "Sidee.icns"
    run("iconutil", "-c", "icns", iconset, "-o", destination)
    return destination


def verify_app(app, architecture):
    """Check data, executable permissions, native slices and collected Tcl/Tk."""
    app = Path(app)
    contents = app / "Contents"
    executable = contents / "MacOS" / "Sidee"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError("The app executable is missing or is not executable.")
    with (contents / "Info.plist").open("rb") as stream:
        metadata = plistlib.load(stream)
    if metadata.get("CFBundleExecutable") != "Sidee":
        raise RuntimeError("The app's Info.plist points to the wrong executable.")
    if not metadata.get("NSLocalNetworkUsageDescription"):
        raise RuntimeError("The app is missing its Local Network permission explanation.")
    resources = contents / "Resources"
    for relative in RESOURCES:
        if not (resources / relative).is_file():
            raise RuntimeError(f"The app is missing {relative}.")
    files = list(contents.rglob("*"))
    if not any(path.name == "init.tcl" for path in files):
        raise RuntimeError("The app is missing the Tcl runtime scripts.")
    if not any(path.name == "tk.tcl" for path in files):
        raise RuntimeError("The app is missing the Tk runtime scripts.")
    expected = "x86_64" if architecture == "x64" else "arm64"
    seen = set()
    native_files = 0
    for path in files:
        if path.is_symlink() and not path.resolve().is_relative_to(app.resolve()):
            raise RuntimeError(f"The app has a link to an external file: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic not in MACHO_MAGICS:
            continue
        slices = run("lipo", "-archs", path, capture_output=True, text=True).stdout.split()
        if slices != [expected]:
            raise RuntimeError(f"Unexpected architecture in {path}: {slices}; expected {expected}.")
        native_files += 1
    if not native_files:
        raise RuntimeError("The app does not contain any Mach-O executables.")
    run("codesign", "--verify", "--deep", "--strict", app)
    print(f"Verified Sidee.app: {native_files} native {expected} files and all dashboard/Tcl/Tk resources.")
    return executable


def verify_dmg(dmg, architecture):
    """Mount the downloadable image read-only and verify its actual contents."""
    run("hdiutil", "verify", dmg)
    with tempfile.TemporaryDirectory(prefix="sidee-dmg-check-") as temporary:
        mount = Path(temporary) / "volume"
        attached = False
        try:
            run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, dmg)
            attached = True
            applications = mount / "Applications"
            if not applications.is_symlink() or os.readlink(applications) != "/Applications":
                raise RuntimeError("The DMG is missing its drag-to-Applications shortcut.")
            for name in ("README.md", "LICENSE", "Install Sidee.txt"):
                if not (mount / name).is_file():
                    raise RuntimeError(f"The DMG is missing {name}.")
            verify_app(mount / "Sidee.app", architecture)
        finally:
            if attached:
                run("hdiutil", "detach", mount)


def package_app(app, architecture):
    distribution = ROOT / "dist"
    name = f"Sidee-macOS-{architecture}"
    archive = distribution / f"{name}.app.zip"
    dmg = distribution / f"{name}.dmg"
    # ditto preserves the symlinks and executable bits in PyInstaller's bundle.
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, archive)
    with tempfile.TemporaryDirectory(prefix="sidee-dmg-") as temporary:
        staging = Path(temporary) / "Sidee"
        staging.mkdir()
        run("ditto", app, staging / "Sidee.app")
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        for name in ("README.md", "LICENSE"):
            shutil.copyfile(ROOT / name, staging / name)
        (staging / "Install Sidee.txt").write_text(
            "Drag Sidee.app to Applications, then open Sidee from Applications.\n\n"
            "This first macOS build has no verified Developer ID signature. If macOS\n"
            "blocks the first opening, use System Settings > Privacy & Security >\n"
            "Open Anyway for Sidee. See README.md for network permissions and help.\n",
            encoding="utf-8",
        )
        run("hdiutil", "create", "-volname", "Sidee", "-srcfolder", staging,
            "-format", "UDZO", "-ov", dmg)
    verify_dmg(dmg, architecture)
    # Verify that the ZIP really retains a runnable, internally linked app.
    with tempfile.TemporaryDirectory(prefix="sidee-zip-check-") as temporary:
        run("ditto", "-x", "-k", archive, temporary)
        verify_app(Path(temporary) / "Sidee.app", architecture)
    print(archive)
    print(dmg)
    return archive, dmg


def build(architecture, version="0.1.1", app_only=False, package_only=False):
    if sys.platform != "darwin":
        raise RuntimeError("macOS bundles must be built on macOS; use the GitHub Actions workflow.")
    architecture = normalized_architecture(architecture)
    if normalized_architecture(platform.machine()) != architecture:
        raise RuntimeError("Use a native runner for the requested architecture.")
    version = validate_version(version)
    app = ROOT / "dist" / "Sidee.app"
    if not package_only:
        make_icon()
        environment = os.environ.copy()
        environment["SIDEE_TARGET_ARCH"] = "x86_64" if architecture == "x64" else "arm64"
        environment["SIDEE_BUILD_VERSION"] = version
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", ROOT / "dist", "--workpath", ROOT / "build" / "macos" / "pyinstaller",
            ROOT / "packaging" / "macos.spec", cwd=ROOT, env=environment)
    verify_app(app, architecture)
    if not app_only:
        package_app(app, architecture)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=("arm64", "x64"),
                        default=normalized_architecture(platform.machine()))
    parser.add_argument("--version", default=os.environ.get("SIDEE_BUILD_VERSION", "0.1.1"))
    stages = parser.add_mutually_exclusive_group()
    stages.add_argument("--app-only", action="store_true",
                        help="Build the app before a future signing/notarization step.")
    stages.add_argument("--package-only", action="store_true",
                        help="Package an existing signed/notarized app without rebuilding it.")
    arguments = parser.parse_args()
    print(build(arguments.architecture, arguments.version,
                arguments.app_only, arguments.package_only))


if __name__ == "__main__":
    main()
