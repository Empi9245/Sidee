<p align="center"><img src="assets/sidee-logo.png" width="180" alt="Sidee"></p>

# Sidee

Install **third-party web apps on Hisense VIDAA TVs** as permanent launcher tiles,
including **Stremio, Nuvio and Jellyfin**. Sidee is a simple **VIDAA sideload**
tool that works with one click from your computer's browser.

Pairing and TV control run **locally** on your network, without an account
or a cloud service. Windows first-time setup downloads Python and its connection
library from their official sources; the macOS app includes them. Pairing requires
the PIN displayed on
**your** TV screen: only you can authorize it.

## Requirements

- Windows 10/11, or macOS 15+ on Apple Silicon or Intel
- Internet access for the first Windows setup and for online TV apps
- Computer and TV on the same Wi-Fi/Ethernet network
- A VIDAA TV (tested on firmware U09.60 / V0000.09.60A.Q0707)

## Install and start

### Windows

1. [Download Sidee for Windows](https://github.com/Empi9245/Sidee/releases/download/v0.1.1/sidee-windows.zip)
   and choose **Extract all**. Open the extracted folder.
2. Double-click **`start-windows.bat`**.
3. Wait for your dashboard to open in the browser. Everything else happens there.

The first launch downloads a private copy of Python and the TV connection
library into `.runtime/`. You do not need to install Python, enter commands,
or copy certificates. Later launches reuse these files without downloading
them again. Administrator rights are not needed.

Keep the launcher's window open while using the dashboard. Double-clicking
the launcher again reopens the dashboard already running for that folder.
If the browser does not open automatically, use the complete link printed
beside `this computer`, including its `?key=...` part. If Windows asks about
network access, allow the app on your private home network so it can find the TV.

Setup uses the [official Python embeddable distribution](https://www.python.org/downloads/release/python-31316/)
and [Eclipse Paho from PyPI](https://pypi.org/project/paho-mqtt/2.1.0/), with
pinned versions and SHA-256 verification. They stay inside the extracted
folder. The TV client certificate bundle is included with the app;
your own TV PIN is still required to authorize pairing. Saved TV tokens
stay in your user profile and are never included in the download.

### macOS

The macOS download contains **Sidee.app** with Python and its dependencies.
It opens the same browser dashboard as Windows, with a small control window
containing **Open dashboard** and **Quit Sidee**. No Python installation or
Terminal window is needed.

1. Open [Build Sidee in GitHub Actions](https://github.com/Empi9245/Sidee/actions/workflows/build.yml)
   and select a successful run for the commit you want. In **Artifacts**, download
   **Sidee-macOS-arm64** for an Apple Silicon Mac (M-series), or
   **Sidee-macOS-x64** for an Intel Mac. GitHub requires sign-in to download
   workflow artifacts. Each artifact contains a `.dmg` and a `.app.zip`.
   Published downloads, when available, are on the [Releases page](https://github.com/Empi9245/Sidee/releases).
2. Extract the artifact ZIP, open `Sidee-macOS-arm64.dmg` or
   `Sidee-macOS-x64.dmg`, and drag **Sidee.app** onto **Applications**.
   Eject the disk image, then open Sidee from Applications.
3. This first version is not signed with a Developer ID or notarized.
   macOS may say **"developer cannot be verified"** or that Apple cannot
   check the app. After trying to open it once, go to **System Settings →
   Privacy & Security → Open Anyway**, then confirm **Open**. Follow
   [Apple's normal procedure](https://support.apple.com/en-us/102445)
   only for a download you trust.
4. If macOS asks to find devices on your local network, allow Sidee.
   If it asks about incoming connections, allow Sidee on your home network
   so your phone can open its dashboard. Then follow the pairing steps below.

Keep Sidee's control window open while using the dashboard. **Open dashboard**
reopens the browser; **Quit Sidee** stops its server. Closing a browser tab does
not stop the app. The download uses separate native Apple Silicon and Intel
builds; it is not a Universal Binary. The app requires macOS 15 or later;
CI builds and checks both architectures on macOS 15.

> La versione macOS viene compilata automaticamente su runner macOS GitHub Actions e necessita ancora di test reali su hardware Mac.

If **Find TV** returns no TV, check that the Mac and TV are on the same home
network, then check **System Settings → Privacy & Security → Local Network**
for Sidee. A VPN, a guest Wi-Fi network, or another active adapter can select
the wrong route. For phone access, check **System Settings → Network →
Firewall → Options** and allow incoming connections for Sidee. See Apple's
[Local Network settings](https://support.apple.com/guide/mac-help/mchla4f49138/mac)
and [firewall settings](https://support.apple.com/guide/mac-help/mh34041/mac).
Sidee does not change these settings itself.

If the app cannot start, its error dialog explains the failure. Startup errors
are also saved in `~/Library/Logs/Sidee/sidee.log`; dashboard runtime state is
under `~/Library/Application Support/Sidee/runtime/`. Pairing tokens continue
to use `~/.sidee/session.json`. Keep tokens and dashboard access links private.

## Pair your TV and install an app

1. **Find TV** — turn on the TV and connect it to the same network as
   your computer, then press **Find TV** in the dashboard.
   Sidee uses the address returned by discovery, without a preset TV IP.
   Saved pairings are reused only after that TV has been found and selected.
2. **Request code** — click **Request code** to display a PIN on your TV.
   Enter those 4 digits in the dashboard's **TV PIN** field and click
   **Confirm code**. Keep the TV on while connecting. If the code expires,
   click **Request code** again to start a new attempt.
3. **Install Apps** — choose **Nuvio**, **Stremio**, or **Jellyfin** in the
   dashboard, wait for confirmation, then open the tile from the TV launcher.
   The Stremio option installs the full **VIDAA TV-adapted Stremio build**,
   not the limited VIDAA Stremio Lite app. It uses the Stremio Theater TV
   interface with a modern Stremio core plus VIDAA-specific D-pad, focus,
   keyboard and viewport fixes. The build is community-maintained by
   [NoobyGains/stremio-vidaa-tv](https://github.com/NoobyGains/stremio-vidaa-tv).
   You can optionally paste a LAN streaming-server URL or the Remote HTTPS URL
   from Stremio Service/Desktop during installation.

The tile stays in the launcher **permanently**, even after unplugging and
restarting the TV: the web app is hosted online, so Sidee does not need to
stay running. If you use Stremio with Stremio Service/Desktop, that streaming
server still needs to be running while you use server-backed playback.


> **Using your phone?** Scan the QR in the dashboard's **Use your phone**
> section with your phone's camera. You can then enter the TV PIN while
> standing beside your TV. Keep your phone, TV and computer on the same
> home network, and leave Sidee running on the computer. A complete
> phone link is also shown below the instructions. On Windows it is also printed
> in the launcher's window. QR generation works locally and is included in both
> downloads.

## Other systems and development

With Python 3.9+ already installed, start the same dashboard with:

```bash
python -m pip install -r requirements.txt
python sidee.py
```

From a repository checkout, build the distributable Windows ZIP with
`python tools/build_windows_release.py`. It includes the app and its
connection bundle, excluding local runtimes, saved sessions, and personal
configuration. The resulting file is `dist/sidee-windows.zip`.

macOS packaging uses PyInstaller to bundle the same Python core into a native
`.app`, then creates a `.dmg` with Apple's disk-image tools. Build instructions,
architecture checks, CI smoke tests, and future signing options are in
[macOS build notes](docs/macos-build.md).

[Build Sidee](https://github.com/Empi9245/Sidee/actions/workflows/build.yml)
checks Windows and both macOS architectures and uploads their packages as
workflow artifacts. A `v*` tag prepares a **draft** GitHub Release containing
the Windows ZIP and both macOS packages; publishing remains a separate step.

To check source changes, run `python -m unittest discover -s tests`.
Dashboard interaction tests use Node.js: `node --test tests/test_dashboard_selection.js`.

Command-line commands (optional):

Replace `TV_IP` with the address shown by **Find TV** on your own network.

```bash
python sidee.py discover           # find TVs
python sidee.py pair TV_IP        # pair (prompts for the PIN)
python sidee.py install nuvio      # register the Nuvio tile
python sidee.py install stremio    # full Stremio TV build for VIDAA
python sidee.py install stremio --server https://YOUR-STREMIO-REMOTE-URL
python sidee.py list               # list launcher tiles
python sidee.py launch nuvio       # launch immediately
python sidee.py refresh            # refresh tokens (last ~30 days)
```

## How it works (briefly)

VIDAA TVs expose a control channel on the local network (MQTT/TLS,
port 36669) used by the official mobile app: SSDP discovery,
PIN pairing, and actions available to paired clients — including
registering web apps in the launcher, just as the phone app does when
you install from the catalog. Sidee is a client for that channel:
the same mechanism, with your app in place of one from the catalog.

## Security and privacy

- **No telemetry**: pairing and TV control communicate with your TV on the
  local network. Windows first-time setup downloads Python and Paho from their
  official sources; the macOS download bundles them.
- Session tokens are stored in `~/.sidee/session.json`
  in your user profile (permissions 600 on Unix; inherited profile
  permissions on Windows). Existing pairings from earlier versions are
  reused automatically, without requiring a new TV PIN.
- The PIN on the TV screen provides consent: pairing requires someone
  in front of the TV
- Available actions are limited to adding/listing/launching web tiles.
  No system writes

## Uninstalling a tile

From the TV launcher: tile context menu → remove (added tiles
can be removed just like Store apps).

## Why this project exists

This tool didn't start with a brilliant idea. It started with many
failed attempts.

I had already spent a whole month trying to install my apps on the TV:
guides, tricks, and methods that led nowhere. Then I gave up.
When I picked it up again, the TV seemed built to say no, and for
a moment, I almost gave up again.

The breakthrough came from understanding one simple thing: the official
phone app talks to the TV locally, and paired clients have the same
permissions. From there, evenings of measurements and experiments became
the three clicks on this page.

I made it with heart, and kept it simple so you don't have to go through
what I did. **If it saved you those weeks, buy me a coffee** it's
the best way to tell me "keep going".

## Support the project

☕ **Ko-fi**: [ko-fi.com/sidee](https://ko-fi.com/sidee)

Configured in `.github/FUNDING.yml`.

## License

MIT — see [LICENSE](LICENSE). This project is independent and not affiliated
with Hisense; trademarks belong to their respective owners. Use it only on
**your own** TV.
