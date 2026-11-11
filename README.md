<p align="center"><img src="assets/sidee-logo.png" width="180" alt="Sidee"></p>

# Sidee

**Your TV, your freedom.**

Sidee is a free, open-source tool that helps people make more of the TVs they already own. Its simple browser dashboard lets you connect to a compatible TV and manage additional web-app launcher tiles, without coding, command-line setup, or specialist knowledge.

Sidee is built around three principles:

- **Freedom and control:** Give people more choice over how they use their own devices.
- **Accessibility:** Make the process straightforward, even for first-time users.
- **Privacy and security:** Keep TV discovery and pairing on the local network, with authorization through the PIN shown on the TV.

## New installer and this client: which one do I need?

Sidee now has a **new installation method**: the Sidee Store installs **real
apps** into the TV tile, one short code at a time. Both are the same site:

- **Sidee Store (new):** https://sidee-native-core.empi-tv.workers.dev/store
- **Download page:** https://sidee-native-core.empi-tv.workers.dev/download

This repository keeps the **original client**, and it stays here unchanged: it
pairs with the TV on your own network (the PIN flow) and writes the first
**Sidee** tile. That tile is the door the store opens: the new installer works
through that tile, it does not replace the client.

**Download one package only, from the download page.** The builds attached to
the Releases page (`v0.1.0` … `v0.1.4.2`) are older snapshots kept for history:
they cannot install the current Sidee tile. Installing both is what produces the
confusion — the old one fails at pairing or opens an outdated dashboard.


## Requirements

- Windows 10/11, macOS 15+ (Apple Silicon or Intel), or Linux with Python 3.9+
- Android 8+ with Termux and Python
- A compatible VIDAA TV and a computer on the same home Wi-Fi/Ethernet network
- Internet access for the initial Windows setup and any online experiences you choose to open on the TV

Compatibility varies by TV model and firmware. The primary tested firmware is U09.60 / V0000.09.60A.Q0707. Support for some other models is experimental; see the [compatibility notes](docs/toshiba-compatibility.md).

## Get started

All four platform packages are published on the
[Sidee download page](https://sidee-native-core.empi-tv.workers.dev/download).
They contain the same reviewed app and a platform-specific launcher:
`sidee-windows.zip`, `sidee-macos.zip`, `sidee-linux.zip`, and
`sidee-android.zip`. The SHA-256 manifest is published at
[`/download/checksums`](https://sidee-native-core.empi-tv.workers.dev/download/checksums).

### Windows

1. [Download Sidee for Windows](https://sidee-native-core.empi-tv.workers.dev/download/sidee-windows.zip) and extract the ZIP.
2. Double-click `start-windows.bat` in the extracted folder.
3. Wait for the dashboard to open in your browser, then follow the on-screen steps.

On first launch, Sidee downloads a private, version-pinned Python runtime and its connection dependency from official sources, verifying the downloads using SHA-256. You do not need to install Python yourself, enter commands, or grant administrator rights. Later launches reuse the downloaded runtime.

Keep the launcher window open while using the dashboard. If the browser does not open automatically, use the full dashboard link shown in the launcher, including its access key. If Windows requests network access, allow it on your trusted home network.

### macOS

The macOS download includes Sidee.app and its required runtime, so no separate Python installation or Terminal commands are needed.

1. Get the package for your Mac from [Releases](https://github.com/Empi9245/Sidee/releases) or a successful [build workflow](https://github.com/Empi9245/Sidee/actions/workflows/build.yml). Choose `arm64` for Apple Silicon or `x64` for Intel.
2. Open the DMG, drag Sidee.app to Applications, and launch it.
3. Use **Open dashboard** in Sidee's control window.

**Important:** The current macOS builds are not signed or notarized. macOS may prevent them from opening automatically. If you trust the downloaded package, follow [Apple's instructions](https://support.apple.com/en-us/102445) for opening an unverified app. If prompted, grant local network access so Sidee can discover your TV. The builds are checked in CI but still require broader testing on physical Macs.

Sidee's control window must remain open while you use the dashboard; **Quit Sidee** stops the local dashboard service.

### macOS source package

[Download the macOS source package](https://sidee-native-core.empi-tv.workers.dev/download/sidee-macos.zip),
extract it, and open `start-macos.command` (or run `sh start-macos.command` in
Terminal). This package uses Python 3.9+ already installed on the Mac. The first
launch creates `.runtime/venv` and installs the TV connection library there.
macOS may block the unsigned `.command` the first time; right-click it and
choose **Open** if you trust the package.

### Linux

[Download the Linux package](https://sidee-native-core.empi-tv.workers.dev/download/sidee-linux.zip),
extract it, and run `./start-linux.sh`. Python 3.9+ is required. On Debian or
Ubuntu install `python3` and `python3-venv`; on Fedora install `python3` and
`python3-virtualenv`. The launcher creates `.runtime/venv` without changing the
system Python. If the browser does not open automatically, open the complete
link printed in the terminal.

### Android (Termux)

Android uses [Termux](https://termux.dev/), not a native APK. Install Termux
from F-Droid or Google Play, then run `pkg update && pkg install python`.
Download [the Android package](https://sidee-native-core.empi-tv.workers.dev/download/sidee-android.zip),
extract it, and run:

```bash
cd Sidee
sh start-android.sh
```

The launcher creates `.runtime/termux-venv`. Keep Termux open while using the
dashboard and use the complete `http://127.0.0.1:...` link it prints. The phone
and TV must be on the same home network.

## Verify downloads

The four packages are built from the same reviewed source tree. Each build
writes a SHA-256 manifest; download it from
[`/download/checksums`](https://sidee-native-core.empi-tv.workers.dev/download/checksums)
and compare it with the downloaded ZIP, for example:

```bash
sha256sum -c SHA256SUMS
```

On macOS use `shasum -a 256 -c SHA256SUMS`. The manifest is also generated for
the GitHub release assets.

## Connect your TV

1. **Find TV:** Turn on your TV, put it on the same network as your computer, and select **Find TV**. Sidee uses the discovered address rather than assuming a fixed TV IP. If discovery fails, you can enter the address shown in the TV's network settings.
2. **Request code:** Select **Request code** and enter the four-digit PIN displayed on your TV, then choose **Confirm code**. Pairing requires this confirmation.
3. **Manage launcher tiles:** Choose an option offered in the dashboard and follow the confirmation steps. The available choices are maintained with Sidee; the dashboard does not currently accept arbitrary web-app URLs.

Registered tiles remain in the TV launcher across restarts, even when Sidee is no longer running. The availability of the web experiences opened by those tiles depends on their own network requirements.

**Want to use your phone?** The dashboard provides a locally generated QR code so you can open its controls on a phone connected to the same home network. Keep Sidee running on the computer and keep dashboard access links private.

## How Sidee works

Sidee uses the TV's local control interface for network discovery, PIN-authorized pairing, and launcher management. The connection uses MQTT/TLS on port 36669. Sidee does not require an account or cloud service for discovery, pairing, or TV control.

Sidee is designed to use functions available to an authorized, paired TV client. It does not install native system software or modify the TV's operating system.

## Privacy and security

- **No Sidee telemetry:** TV discovery and control take place locally; Sidee does not require an account.
- **Consent-based pairing:** You must confirm the PIN shown on your TV.
- **Local credentials:** Saved pairing tokens remain in your user profile at `~/.sidee/session.json` (mode 600 on Unix; inherited user-profile permissions on Windows).
- **Protected dashboard access:** Treat dashboard links and saved pairing tokens as private. Only share access with people you trust on your home network.
- **Limited operations:** Sidee manages web launcher tiles through the TV's authorized control interface; it does not make system-level changes.

The first Windows setup downloads verified dependencies. Web experiences opened from the TV launcher may make their own network connections independently of Sidee.

## Troubleshooting

If **Find TV** cannot locate your TV, check that both devices share the same network and that a VPN, guest Wi-Fi, or firewall is not blocking local discovery. The manual IP option checks that the destination responds as a compatible TV and that port 36669 is reachable; it never bypasses PIN authorization.

Some TVs advertise themselves rather than replying directly to discovery. In that case, keep the TV on and retry **Find TV**. For known firmware-specific pairing limitations, see the [compatibility notes](docs/toshiba-compatibility.md).

On macOS, check **System Settings → Privacy & Security → Local Network** and, if needed, the firewall permissions for Sidee. Diagnostic logs are stored at `~/Library/Logs/Sidee/sidee.log`. Keep logs containing private access data confidential.

## Development

With Python 3.9+ already installed, the dashboard can also be started from a source checkout:

```bash
python -m pip install -r requirements.txt
python sidee.py
```

Optional command-line interface:

```bash
python sidee.py discover
python sidee.py pair TV_IP
python sidee.py install PRESET_ID
python sidee.py list
python sidee.py launch PRESET_ID
python sidee.py refresh
```

Replace `TV_IP` with your TV's LAN address and `PRESET_ID` with an available built-in option. Pairing always requires the TV's authorization.

Run Python tests with `python -m unittest discover -s tests` and dashboard interaction tests with `node --test tests/test_dashboard_selection.js`.

Build all four source packages with `python tools/build_platform_releases.py`;
the command writes `dist/sidee-windows.zip`, `dist/sidee-macos.zip`,
`dist/sidee-linux.zip`, `dist/sidee-android.zip`, and `dist/SHA256SUMS`.
Packaging information is in the [macOS build notes](docs/macos-build.md). The
[Build Sidee workflow](https://github.com/Empi9245/Sidee/actions/workflows/build.yml)
runs Windows, native macOS, and Linux source-package jobs; the release job adds
a combined `SHA256SUMS` to the draft assets.

## Why Sidee exists

Sidee began with a simple idea: people should have more freedom to use technology they already own. After a lot of experimentation, that idea became a small tool designed to make everyday tasks easier and more approachable. If it helps you, please consider supporting continued development.

☕ [Support Sidee on Ko-fi](https://ko-fi.com/sidee)

## License

MIT — see [LICENSE](LICENSE). Sidee is an independent project and is not affiliated with TV manufacturers. Use it only with devices you own or are authorized to manage.
