"""Fail closed on unexpected release inputs, private policy matches and local state.

Policy fingerprints avoid copying private implementation terms into this repo.
They detect known tokens, not all possible transformations of private code.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

CORE_MODULES = (
    "__init__.py", "_qrcodegen.py", "client.py", "native_api.py",
    "native_session.py", "pairing.py", "phone.py", "platform_support.py",
    "presets.py", "protocol.py", "webui.py",
)
TOP_LEVEL = ("README.md", "LICENSE", "requirements.txt", "sidee.py",
             "start-windows.bat", "start-windows.ps1")
ASSETS = ("sidee-logo.png", "nuvio-wordmark.png", "jellyfin.png")
PUBLIC_FILES = (*TOP_LEVEL, *("core/" + n for n in CORE_MODULES),
                "core/dashboard.html", "core/tv-client.bundle",
                *("assets/" + n for n in ASSETS))
PRIVATE_PARTS = frozenset((
    ".git", ".opencode", ".zcode", ".freebuff", ".wrangler", ".sidee",
    ".vidaa-tile", ".runtime", ".venv", ".private", "node_modules",
    "sidee-native-core", "forge",
    ".secrets", ".audit", "__pycache__",
))
PRIVATE_PATH_FINGERPRINTS = frozenset((
    "fc575664080feba245de011d5edc9a5087ed082322e307baf7049c7756a90cf7",
    "3ff9f622ebb1e99b7f0a121c5d551508fdd72b5bd5fb50f4e5d483713c2519cf",
    "06dbe9437b341a00bd590e5217ec5e457bd601372dacfae28454fb3a0e5b978e",
))
PRIVATE_NAMES = frozenset((
    "session.json", "dashboard.json", "presets_local.py", ".env", ".dev.vars",
    "metodi_installazione_app.md", "vidaa_dev_book.md", "vidaa_case_index.md",
    "sidee-native-architettura.md", "sidee-monetizzazione.md",
))
TOKEN_FINGERPRINTS = frozenset((
    "0b34adc7590633b3c25999682a51b0279722b2a63d1b90e6494aa269760f0eda",
    "1995ac702bba1d6283e22964a69cb18c855bc8e0e24cce1d057670bc12ff2ba6",
    "1a9e6a3a4deecfd36f4ff00b46bdf62f56ba8af63d71499160dbfd831940ceb5",
    "1f87635aff05d8cfd5081f572fc9c14d7b14b4f40cbf6b6f077437c48ac844e7",
    "21414d8a805b190a9fdc6b04c56168ff0ed032398d2aa2e5d035a6e003ab507e",
    "5777bc1edcc567c9bad88edefc3146e0012864245f0eb623a24c7abe48c838f1",
    "8a444598e5fc6fd1dc14a75a7688e18f129d09e73e1446e392937849a1eb9c0b",
    "92c4b403848c4c9be3929cab966d2c2b34772179d7318c581055e5a9dd9f1dec",
    "9ae801ffbabc01110c504edb9b97915203b6c814c55b034eb783b7a2510601b2",
    "adde73956e80fa10e12dbd4783f889c1b051a815454f9f0a5b9ef9ab3a977f01",
    "afd8c698653a39b2bb2c471960170b68f315c2e000928db9adf0a185e509e72a",
    "f45d5cdaac7fad4b4ccb5eba515556ed763cc234acc37c1b72a37b656c0a673d",
))
TEXT_SUFFIXES = frozenset((".py", ".js", ".ts", ".html", ".md", ".json", ".bundle", ".css", ".svg",
                           ".toml", ".yml", ".yaml", ".txt", ".ps1", ".bat"))
MAX_TEXT_BYTES = 2_000_000


class ReleaseBoundaryError(ValueError):
    pass


def check_name(name):
    p = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or p.is_absolute()
            or ".." in p.parts or p.as_posix() != name or any(ord(c) < 32 for c in name)):
        raise ReleaseBoundaryError("Non-canonical release path")
    lower = p.name.lower()
    if (any(n.lower() in PRIVATE_PARTS or hashlib.sha256(n.lower().encode()).hexdigest() in PRIVATE_PATH_FINGERPRINTS for n in p.parts) or lower in PRIVATE_NAMES
            or lower.startswith((".env.", ".dev.vars.", "audit-sidee-native"))
            or lower.endswith(".map")):
        raise ReleaseBoundaryError(f"Private/local path blocked: {name}")


def check_content(name, data):
    if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
        return
    if len(data) > MAX_TEXT_BYTES:
        raise ReleaseBoundaryError(f"Text release input too large: {name}")
    # Whole tokens: a harmless port containing a shorter numeric ID must pass.
    tokens = set(re.findall(rb"[A-Za-z_][A-Za-z_0-9]*|[0-9]+", data.lower()))
    if any(hashlib.sha256(t).hexdigest() in TOKEN_FINGERPRINTS for t in tokens):
        raise ReleaseBoundaryError(f"Private implementation policy match: {name}")
    if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----(?:[ \t\r\n]|\\[nr]|['\"+])+[A-Za-z0-9+/=]{64,}", data):
        raise ReleaseBoundaryError(f"Private key material blocked: {name}")
    if re.search(rb"\bsb_secret_[A-Za-z0-9_-]{16,}\b|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{12,}\b", data):
        raise ReleaseBoundaryError(f"Secret-like credential blocked: {name}")
    # The update signer exports PKCS8 as plain base64, without a PEM header.
    # PrivateKeyInfo begins with an INTEGER version followed by an algorithm
    # SEQUENCE; public SPKI keys do not have that version field.
    for encoded in re.findall(rb"[A-Za-z0-9+/]{120,}={0,2}", data):
        if len(encoded) > 8192:
            continue
        try:
            der = base64.b64decode(encoded, validate=True)
        except ValueError:
            continue
        if len(der) < 12 or der[0] != 0x30:
            continue
        offset = 2 + (der[1] & 0x7f) if der[1] & 0x80 else 2
        if der[offset:offset + 3] in (b"\x02\x01\x00", b"\x02\x01\x01") and der[offset + 3:offset + 4] == b"\x30":
            raise ReleaseBoundaryError(f"Encoded private key material blocked: {name}")
    keys = re.findall(rb"\bSN-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}\b", data)
    if any(k != b"SN-XXXX-XXXX-XXXX" for k in keys):
        raise ReleaseBoundaryError(f"Activation key-like value blocked: {name}")


def check_sources(root, files):
    root = Path(root).resolve()
    for file in files:
        file = Path(file)
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ReleaseBoundaryError("Release input is a link or outside the project")
        name = file.relative_to(root).as_posix()
        check_name(name)
        if not file.is_file():
            raise FileNotFoundError(f"Release file is missing: {name}")
        if file.suffix.lower() in TEXT_SUFFIXES:
            with file.open("rb") as stream:
                check_content(name, stream.read(MAX_TEXT_BYTES + 1))


def check_public_source(root):
    root = Path(root).resolve()
    unexpected = {p.name for p in (root / "core").glob("*.py")} - set(CORE_MODULES) - {"presets_local.py"}
    if unexpected:
        raise ReleaseBoundaryError("Unreviewed core modules: " + ", ".join(sorted(unexpected)))
    files = [root / name for name in PUBLIC_FILES]
    if (root / "macos_launcher.py").is_file():
        files.append(root / "macos_launcher.py")
    check_sources(root, files)


def check_zip(path):
    expected = {"Sidee/" + name for name in PUBLIC_FILES}
    seen = set()
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            name = entry.filename
            check_name(name.rstrip("/"))
            if entry.is_dir():
                continue
            if name.casefold() in seen or name not in expected or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ReleaseBoundaryError("Unexpected, duplicate or linked ZIP member: " + name)
            seen.add(name.casefold())
            if PurePosixPath(name).suffix.lower() in TEXT_SUFFIXES:
                if entry.file_size > MAX_TEXT_BYTES:
                    raise ReleaseBoundaryError("ZIP text input too large: " + name)
                check_content(name, archive.read(entry))
        if seen != {name.casefold() for name in expected}:
            raise ReleaseBoundaryError("The release archive is missing required files")
    return len(seen)


def check_commit(root, revision):
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64}|HEAD)", revision):
        raise ReleaseBoundaryError("Expected a commit object ID or HEAD")
    root = Path(root)
    files = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision], cwd=root).split(b"\x00")
    texts = []
    for raw in filter(None, files):
        meta, raw_name = raw.split(b"\t", 1)
        mode, kind, oid = meta.split()
        name = raw_name.decode("utf-8", "strict")
        check_name(name)
        if PurePosixPath(name).suffix.lower() in TEXT_SUFFIXES:
            if mode == b"120000" or kind != b"blob":
                raise ReleaseBoundaryError("Linked source input blocked: " + name)
            texts.append((name, oid))
    # One bounded streaming Git process per commit, not one process per file.
    process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for name, oid in texts:
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256).split()
            if len(header) != 3 or header[1] != b"blob":
                raise ReleaseBoundaryError("Cannot inspect Git source input")
            size = int(header[2])
            if size > MAX_TEXT_BYTES:
                raise ReleaseBoundaryError("Git text input too large: " + name)
            data = process.stdout.read(size)
            if len(data) != size or process.stdout.read(1) != b"\n":
                raise ReleaseBoundaryError("Incomplete Git source input")
            check_content(name, data)
        process.stdin.close()
        if process.wait(timeout=10) != 0:
            raise ReleaseBoundaryError("Git source inspection failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zip", type=Path)
    group.add_argument("--source-root", type=Path)
    group.add_argument("--git-commit")
    args = parser.parse_args()
    try:
        if args.zip:
            check_zip(args.zip)
        elif args.source_root:
            check_public_source(args.source_root)
        else:
            check_commit(Path.cwd(), args.git_commit)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Publication blocked: {error}\n")
    print("Public release boundary check passed.")


if __name__ == "__main__":
    main()
