# Rebuilding the published packages

The four source packages served from `/download/sidee-<platform>.zip` are built
from this repository only. The build uses a fixed timestamp for every ZIP entry,
so a checkout of the same commit produces the same bytes on any machine.

```sh
python tools/build_platform_releases.py
sha256sum dist/sidee-windows.zip
# a18befc2e600a5d4dc4c782145062fe92fc052cbb8c0bdb56a8fe6163ad81df2  dist/sidee-windows.zip
```

Expected output for the packages published with commit `fc497d9` (fixed
timestamps, `PUBLIC_FILES` order, content only):

| File | SHA-256 |
|---|---|
| `sidee-windows.zip` | `a18befc2e600a5d4dc4c782145062fe92fc052cbb8c0bdb56a8fe6163ad81df2` |
| `sidee-macos.zip` | same bytes as Windows (same source tree) |
| `sidee-linux.zip` | same bytes as Windows |
| `sidee-android.zip` | same bytes as Windows |

`SHA256SUMS` is generated next to the archives. The APK has its own hash
(`e6338cc3…`) and is not rebuilt by this command.

To update the Worker's KV copy, from the Worker project:

```sh
npx wrangler kv key put --namespace-id=<namespace> --remote \
  download:sidee-windows --path ../vidaa-tile/dist/sidee-windows.zip
# repeat for macos, linux, android, then download:checksums
```

Verify the live copy:

```sh
curl -s https://sidee-native-core.empi-tv.workers.dev/download/sidee-windows.zip \
  | sha256sum
```

The served hash must equal the table above. A build from a clean clone of the
commit is the release check; a dirty working tree is not evidence.
