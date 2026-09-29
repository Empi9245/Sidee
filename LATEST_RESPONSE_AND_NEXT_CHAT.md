# Sidee — native VIDAA key routing test

Date: 2026-09-29

Current confirmed behavior:
- Sidee raw-IP page receives no DOM key events at all;
- programmatic focus briefly appears, but OK is consumed outside the page and focus disappears;
- therefore normal JS keydown fixes cannot solve dashboard navigation.

Research result:
Historical Hisense launcher code explicitly switches key ownership when opening apps/web-apps:
- `hiWebOsFrame.registerKeyCodesForAppExcludeKey()`
- internally uses `keyboard.registerKeyCodes(...)`
- then `keyboard.setWantGroup(0)`

This routing keeps system keys with the launcher while allowing normal app keys (D-pad/Enter) to reach the app/web runtime.

Implemented:
- commit `f5b5a9b8d593081487793e2020e122887c7e386b`
- automatic `nativeKeyRoutingProbe` on Sidee page load
- if `hiWebOsFrame.registerKeyCodesForAppExcludeKey` is exposed, Sidee invokes that exact launcher routine
- otherwise, if the lower-level `keyboard` bridge and enough known VK constants are exposed, Sidee reproduces the same launcher routing using `registerKeyCodes` + `setWantGroup(0)`
- no click is required
- result is saved in `nativeKeyRoutingProbe`

Next:
1. `git pull --ff-only origin main`
2. fully restart Sidee as Administrator
3. close and reopen the TV page
4. try arrows + OK
5. reply `fatto keys`

Then inspect:
- `nativeKeyRoutingProbe`
- `remoteInputProbe.events`

If success=true and raw key events appear, Sidee dashboard can be made fully D-pad navigable.
If both native bridges are unavailable, raw browser context cannot claim D-pad ownership and future tests should be run automatically or from a true app container.
