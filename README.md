# HideMyEmulator 1.3 → Premium patch

Reproducible smali patch for `net.wowsoftware.hidemyemulator` 1.3 (versionCode 4)
that forces lifetime-premium license state. Verified on-device (Infinix, LSPosed):
pill shows **Premium**, all 12 protections toggleable, no trial sheet.

![proof](proof.png)

## Patch sites (all in `patch.py`)

| # | File | What |
|---|---|---|
| 1 | `smali/o9/a.smali` | `a(Lz9/h;J)Lo9/k` mapper always returns `new o9/h(null, null)` (lifetime premium, no expiry) |
| 2 | `smali/o9/c.smali` | license-query exception fallback `o9/j` → `o9/h(null, null)` |
| 3 | `smali/ba/u.smali` | license combine (`:cond_5`) always emits premium `ba/s` |
| 4 | `smali/ba/v.smali` | initial license state `Lo9/i` → `o9/h(null, null)` |
| 5 | `smali/net/wowsoftware/hidemyemulator/core/ModuleStatus.smali` | `isModuleActive()` `false` → `true` |

Why the source, not the UI: the Xposed hook (`aa/f`, `w9/o`) never checks the
license — only the UI gates the protection toggles. Forcing the `o9/k` license
state unlocks everything downstream (pill, cards, chat intent).

## Usage

Requires: Apktool 3.0.3, Android build-tools (apktool/`aapt2`, `zipalign`,
`apksigner`), JDK.

```sh
python patch.py --apk release-1.3.apk --out patched-premium-signed.apk
```

Options: `--apktool`, `--build-tools`, `--keystore/--storepass/--keypass/--keyalias`
(defaults to the debug keystore; without `--keystore` an ephemeral key is
generated), `--no-sign`, `--workdir`. JVM heap is capped internally so it also
builds on machines with a small pagefile.

Install:

```sh
adb install -r patched-premium-signed.apk
```

Then in LSPosed Manager enable the module + scope, **reboot**, toggle
protections → Apply.

## Notes

- Output is signed with a debug/ephemeral key, not the dev key. Uninstall any
  official-signed copy first if signatures clash.
- `release-1.3.apk` (original input) is not committed; place it next to the script.
