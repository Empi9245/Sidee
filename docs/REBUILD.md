# Rebuilding the published packages

The four source packages are built from this repository only and published
through GitHub: as the `Sidee-source-platforms` workflow artifact, and as
release assets when the release job attaches them. The build uses a fixed
timestamp for every ZIP entry, so a checkout of the same commit produces the
same bytes on any machine.

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

Attach the four ZIPs and `SHA256SUMS` to the GitHub release. Do not upload them
to the new Sidee site: the original GitHub Sidee and the new online-store
version are separate products.

Verify the archives locally:

```sh
sha256sum -c dist/SHA256SUMS
```

A build from a clean clone of the commit is the release check; a dirty working
tree is not evidence.
