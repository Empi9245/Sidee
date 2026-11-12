# Brand-specific VIDAA authentication compatibility

Reported target, 13 October 2026: Toshiba Z670, firmware
`V0000.09.60N.Q0615`, extended version `X0003.W01.Y01.J01`, minor version
`N.Q0615.9.61.00-a20260727u`. The reporter confirms that the official VIDAA app
pairs and controls the TV. Sidee reports MQTT `rc=5` before displaying its PIN.
No local pairing or installation on this model has been verified yet.

Firmware version alone does not identify the required authentication algorithm.
MQTT 3.1.1 code 5 is an authorization refusal after the connection reaches the
TV. Discovery and official remote control are useful evidence, but neither
confirms that this model accepts Sidee's app-install action.

## Implemented behavior

- Try static authentication first on fresh pairing. After
  an explicit authentication refusal (4 or 5), try modern, middle, and RemoteNOW
  profiles once each. Close each rejected connection before opening another.
  Stop on TLS, network, timeout, or other broker errors.
- Use the saved profile first when pairing the same TV again. Reuse its client
  identity; do not reuse a different TV's saved pairing identity.
- On static firmware, request TV state to trigger the PIN. If no PIN notification
  arrives, try the documented VIDAA app-connect request. PIN acceptance remains
  mandatory for saving a new pairing.
- Request tokens after PIN acceptance. Only a static profile with no token
  response can proceed without tokens, and it must answer a fresh app-list
  request. Invalid or incomplete token responses remain errors.
- Preserve the accepted profile, client ID, and username on reconnection and
  token refresh. Static pairings have no token expiry or automatic refresh.
- If a saved static pairing is rejected, ask for a new PIN. Do not change
  authentication profiles while running an installation.
- Accept VIDAA identifiers in a Toshiba UPnP descriptor without requiring the
  manufacturer to be Hisense. Toshiba branding alone does not identify VIDAA.

## Any VIDAA brand, not just Toshiba

The value is not an HTTP path or a hardcoded “Toshiba mode”. The TV advertises
its own brand in the UPnP `modelDescription`, for example:

```text
transport_protocol=3290
brand=tos
```

Sidee reads that value (case-insensitive key) and uses it in the MQTT client
identity, username and password derivation. The same works for any badge that
runs VIDAA and declares its own code: a Tesla-branded set that advertises
`brand=tes` is tried with `tes`, not with a fixed `his`. If the descriptor has
no `brand=` line, Sidee keeps the historical `his` fallback; that is the only
case where the badge cannot be inferred, and a `rc=5` refusal is the expected
symptom. The official app's headers are not required when the descriptor
already carries the field: collect `manufacturer`, `modelName`,
`modelDescription` (`brand=`, `transport_protocol=`) and the exact Sidee error
before assuming a different algorithm.

This brand fix only affects connecting to the TV and registering the Sidee
tile. It does not change how the new method writes an app into the tile: a
successful pairing is not proof that the tile can be installed. Those are two
different failures and must be reported separately.

## Brand fix (0.1.4.2, 13 October 2026)

Root-cause candidate identified and implemented for the `rc=5` refusal on
the reported Z670: Sidee hardcoded `brand="his"` in the credential
derivation, while the Toshiba descriptor itself declares `brand=tos`. The
official app's native library takes the brand as an **input** to the same
algorithm (`getConnectUser(uuid, brand, operation, time, flag)`), and the
reference implementations confirm the shape:

- client_id: `<uuid>$<brand>$<race>_vidaacommon_001`
- username: `<brand>$<timestamp ^ XOR>` (or `<brand>$<timestamp>` for
  RemoteNOW)
- password: `md5("<timestamp>$<md5("<brand><digit><suffix>")[:6]>")` —
  the value suffixes are firmware constants (the 3-slot table in the
  native library) and do **not** change with the brand

Verified offline (10 new tests, full suite 176 green): per-brand
credential structure and determinism, descriptor `brand=` parsing with
fallback, session roundtrip, legacy-session compatibility (missing
`brand` loads as `his`), and brand propagation into every pairing
connection.

**Needs live confirmation on the reported Toshiba:** that the broker
accepts dynamic credentials derived from `brand=tos` (static username and
password stay unchanged; the saved topic identity stays stable while the broker
connection id is unique per connection, as in pyvidaa). The log now
prints `TV declares brand=tos: using it in the credentials` when the
descriptor carries a non-Hisense brand, so a failure on the real TV is
immediately distinguishable from a discovery problem.

## Trial on the reported TV

Extract the experimental Windows ZIP in a new folder, open `start-windows.bat`,
find the TV, and request a code. Enter only the PIN displayed on that TV. If
pairing succeeds, install one app and check the returned app list and launcher.
Close and reopen Sidee to check that the saved pairing reconnects without a new
PIN. Firmware updates and TV restarts should be checked separately.

If connection still fails, collect the authentication profile/result lines
printed by Sidee, the exact dashboard error, and whether a PIN appeared. Do not
share `session.json`, PINs, tokens, or dashboard access links. Successful pairing
alone should not be reported as confirmed tile-install support.

## Protocol references

- [hisense_vidaa credential profiles](https://github.com/stevene1919/hisense_vidaa/blob/main/custom_components/hisense_vidaa/crypto.py)
- [vidaa-control Toshiba static fallback](https://github.com/Lucent-/vidaa-control/blob/main/vidaa/client.py)
- [pyvidaa static PIN and tokenless pairing](https://github.com/warrenrees/pyvidaa/blob/master/pyvidaa/client.py)
- [pyvidaa documented MQTT topics](https://github.com/warrenrees/pyvidaa/blob/master/pyvidaa/topics.py)

Offline tests use simulated TV responses and independent credential vectors.
They validate fallback, PIN confirmation, session persistence, refresh behavior,
and the browser flow; they cannot establish compatibility with this firmware.
