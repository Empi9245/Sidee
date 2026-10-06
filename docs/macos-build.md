# macOS build and validation

Sidee keeps one Python core and one browser dashboard. Windows continues to use
its private embedded Python launcher and source ZIP. macOS uses PyInstaller's
directory bundle to include Python, Paho, Tcl/Tk, the dashboard, its images, and
the TV client certificate bundle inside `Sidee.app`. A small native control
window opens the dashboard and stops the server; it does not replace the web UI.
PyInstaller fits the existing Python entrypoint and supports native app bundles
and architecture checks; see its [macOS options](https://pyinstaller.org/en/stable/usage.html#macos-specific-options).

The directory bundle avoids extracting the runtime at every launch. Writable
dashboard state lives outside the app in
`~/Library/Application Support/Sidee/runtime/`; startup exceptions from the
native launcher are written to `~/Library/Logs/Sidee/sidee.log` without dashboard
keys. Pairings continue to use `~/.sidee/session.json`. Build inputs exclude
personal sessions, local runtimes, and user configuration.

## Architectures and downloads

The [Build Sidee workflow](../.github/workflows/build.yml) builds each architecture
on a native GitHub-hosted macOS 15 runner:

| Mac | Runner | Actions artifact | Files inside |
| --- | --- | --- | --- |
| Apple Silicon | `macos-15` | `Sidee-macOS-arm64` | `Sidee-macOS-arm64.dmg`, `Sidee-macOS-arm64.app.zip` |
| Intel | `macos-15-intel` | `Sidee-macOS-x64` | `Sidee-macOS-x64.dmg`, `Sidee-macOS-x64.app.zip` |

Each artifact contains `Sidee.app`, either in the disk image or in the app ZIP.
The ZIP is made with `ditto --sequesterRsrc --keepParent` so macOS bundle links
and executable permissions survive download. The DMG includes an Applications
shortcut for drag-to-install. These are separate native bundles, not a
Universal Binary. The workflow checks the actual bundle architecture. The app
declares macOS 15.0 as its minimum version, matching the CI baseline; older
macOS versions are not supported by these bundles.

Download artifacts from a successful run on the
[Actions page](https://github.com/Empi9245/Sidee/actions/workflows/build.yml).
GitHub requires sign-in for artifact downloads. On a `v*` tag, the workflow also
creates or updates a **draft** release with `sidee-windows.zip` and both Mac
DMG/app ZIP pairs. A maintainer reviews that draft before publication; ordinary
branch builds do not publish a release.

## Build on macOS

CI uses Python 3.13.16, Paho 2.1.0, and PyInstaller 6.22.3 with pinned packaging
dependencies. Building locally needs a Mac of the target architecture, but end
users do not need Python. The workflow
contains the complete dependency-install and build commands and is the reference
for a clean build. The macOS release builder runs PyInstaller, packages the app,
and creates the disk image with the system `hdiutil` tool. After installing the
build dependencies on macOS, run:

```bash
python -m pip install -r requirements-build-macos.txt
python tools/build_macos_release.py --architecture arm64
```

Use `--architecture x64` on Intel. Outputs are `dist/Sidee.app` and the
architecture-labelled `.app.zip` and `.dmg` files in `dist/`.

Do not build an arm64 bundle using an Intel interpreter or the reverse. The
build rejects an architecture mismatch rather than labelling a foreign bundle
as native. Sidee's application dependencies are shared between platforms; only
the launcher, interface enumeration, runtime paths, and packaging differ.

## Automated checks

The macOS jobs run the Python suite and the Node dashboard interaction tests,
check imports, and build the real `.app`. Checks include:

- A source startup test using `--headless --port 0`, with isolated state via
  `SIDEE_STATE_DIR`, and HTTP requests to status, phone-access, and static assets.
- `--self-test` on the packaged executable, including Tcl/Tk availability and
  loading the bundled TLS client certificate without connecting to a TV.
- Startup of `Sidee.app/Contents/MacOS/Sidee` itself in headless mode, requests
  to its local dashboard, and clean process shutdown and runtime-state cleanup.
- Inspection of bundled assets, every Mach-O binary's native architecture,
  internal bundle links, Tcl/Tk resources, signatures, the mounted DMG,
  and an app-ZIP extraction roundtrip.
- Checks that the macOS path does not invoke Windows-only commands.

The headless checks do not open a browser or create an interactive GUI. They do
not scan for, pair with, or control a TV. The Windows job runs the shared suites
and checks its real first-launch runtime preparation before packaging the ZIP.

These checks validate the packaged server on real macOS runners. They cannot
verify Finder launch, native window appearance, Gatekeeper's downloaded-app
prompts, local-network permission prompts, or discovery/pairing on a home LAN.
Apple documents that command-line tools launched from Terminal or SSH have a
[Local Network permission exception](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy),
so a shell-based CI run cannot prove that Finder launch obtains that permission.
Real Mac testing still needs first launch from a downloaded DMG, Allow/Open
Anyway flows, Wi-Fi/Ethernet discovery with multiple interfaces, phone access,
PIN pairing, tile registration, and app quit/relaunch.

> La versione macOS viene compilata automaticamente su runner macOS GitHub Actions e necessita ancora di test reali su hardware Mac.

## First release and future signing

The first app is not signed with an Apple Developer ID or notarized. PyInstaller
may apply an ad-hoc signature needed to run native code; that does not identify
the developer or provide notarization. Follow
[Apple's Open Anyway procedure](https://support.apple.com/en-us/102445) after
the first blocked launch. Sidee does not disable Gatekeeper or remove quarantine.

To add signing later, keep the Developer ID certificate and its password in
GitHub Actions secrets and import them into an ephemeral runner keychain. Pass
the installed signing identity through `SIDEE_CODESIGN_IDENTITY`, then verify the
result with `codesign --verify --deep --strict`. Do not commit a certificate,
private key, password, or notarization credential.

`SIDEE_ENTITLEMENTS_FILE` optionally supplies an entitlements file for that signed
build. Use the builder's `--app-only` option to create the app before the
notarization step and `--package-only` to package it after approval and stapling.

Notarization is a later release step, following
[Apple's notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow): submit the signed package using
`xcrun notarytool submit --wait` with credentials supplied through the runner,
check the result, and staple the accepted ticket to the app using
`xcrun stapler staple`. A ZIP cannot be stapled directly. Recreate the app ZIP/DMG
when stapling changes its contents, validate the final
packages, and upload those files as the release assets. The unsigned build does
not require Apple Developer membership; a future Developer ID release does.

The app declares why it needs the local network. It uses the existing SSDP
discovery and MQTT/TLS control protocol, not Bonjour service discovery, and
does not alter the firewall. Apple documents the user controls under
[Privacy & Security → Local Network](https://support.apple.com/guide/mac-help/mchla4f49138/mac)
and [Network → Firewall](https://support.apple.com/guide/mac-help/mh34041/mac).
