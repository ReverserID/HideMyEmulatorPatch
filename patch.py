#!/usr/bin/env python3
"""HideMyEmulator 1.3 -> premium patch.

Reproducible pipeline: decode -> patch 5 smali sites -> rebuild -> align -> sign.
Tested with: Apktool 3.0.3, build-tools 36.0.0, release-1.3.apk (vCode 4).

Usage:
    python patch.py --apk release-1.3.apk --out patched-premium-signed.apk
    [--apktool C:/bin/apktool/apktool.jar] [--build-tools ANDROID_HOME/build-tools/36.0.0]
    [--keystore ~/.android/debug.keystore --storepass android --keypass android]
    [--no-sign] [--workdir build]

If --keystore is omitted, an ephemeral signing key is generated with keytool.
Low-memory safe: JVM calls are capped via _JAVA_OPTIONS (pagefile-friendly).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

JAVA_OPTS = "-Xmx384M -XX:+UseSerialGC"
JAVA_SIGN_OPTS = "-Xmx256M"


def run(cmd, env_extra=None, **kw):
    env = dict(os.environ)
    env.update(env_extra or {})
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, env=env, **kw)


def replace_once(path, pattern, repl, desc, must_contain=None):
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    src = raw.replace("\r\n", "\n")
    new, n = re.subn(pattern, repl, src, count=1, flags=re.DOTALL)
    if n != 1:
        sys.exit(f"PATCH FAILED [{desc}]: anchor matched {n}x in {path}")
    for anchor in must_contain or []:
        if anchor not in new:
            sys.exit(f"PATCH FAILED [{desc}]: result missing {anchor!r} in {path}")
    if crlf:
        new = new.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print(f"patched [{desc}]")


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


# 1. License mapper: o9/a.a() always returns lifetime premium.
def patch_mapper(smali):
    p = os.path.join(smali, "o9", "a.smali")
    replace_once(
        p,
        r"\.method public static a\(Lz9/h;J\)Lo9/k;.*?\.end method",
        """.method public static a(Lz9/h;J)Lo9/k;
    .locals 1
    new-instance p0, Lo9/h;
    const/4 v0, 0x0
    invoke-direct {p0, v0, v0}, Lo9/h;-><init>(Ljava/lang/String;Ljava/lang/Long;)V
    return-object p0
.end method""",
        "o9/a mapper -> premium",
    )


# 2. License query exception fallback: o9/j -> lifetime premium.
def patch_query_fallback(smali):
    p = os.path.join(smali, "o9", "c.smali")
    replace_once(
        p,
        r"(invoke-static \{v0, v1, p1\}, Landroid/util/Log;->w\(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;\)I\n.*?)\s*sget-object p1, Lo9/j;->a:Lo9/j;",
        r"""\1
    new-instance p1, Lo9/h;
    const/4 v0, 0x0
    invoke-direct {p1, v0, v0}, Lo9/h;-><init>(Ljava/lang/String;Ljava/lang/Long;)V""",
        "o9/c exception fallback -> premium",
    )


# 3. License combine: ba/u always emits premium ba/s.
def patch_combine(smali):
    p = os.path.join(smali, "ba", "u.smali")
    replace_once(
        p,
        r"(:cond_5\n    check-cast v2, Lba/v;).*?invoke-direct \{v3, v0, v1, p1, v2\}, Lba/s;-><init>\(Lo9/k;Ljava/lang/Long;ZZ\)V",
        """:cond_5
    check-cast v2, Lba/v;

    .line 121
    .line 122
    iget-boolean p1, v2, Lba/v;->c:Z

    .line 123
    new-instance v0, Lo9/h;

    .line 124
    const/4 v1, 0x0

    invoke-direct {v0, v1, v1}, Lo9/h;-><init>(Ljava/lang/String;Ljava/lang/Long;)V

    const/4 v1, 0x0

    const/4 v2, 0x1

    .line 125
    .line 126
    new-instance v3, Lba/s;

    .line 127
    .line 128
    invoke-direct {v3, v0, v1, p1, v2}, Lba/s;-><init>(Lo9/k;Ljava/lang/Long;ZZ)V""",
        "ba/u combine -> premium",
    )


# 4. License initial state: ba/v Lo9/i -> lifetime premium.
def patch_initial(smali):
    p = os.path.join(smali, "ba", "v.smali")
    replace_once(
        p,
        r"    const/16 v3, 0xb.*?    :goto_0",
        """    new-instance v3, Lo9/h;

    .line 67
    const/4 v5, 0x0

    invoke-direct {v3, v5, v5}, Lo9/h;-><init>(Ljava/lang/String;Ljava/lang/Long;)V

    .line 70
    .line 71
    .line 74
    .line 75
    :goto_0""",
        "ba/v initial -> premium",
    )


# 5. Module status: isModuleActive() false -> true.
def patch_module_status(smali):
    p = os.path.join(
        smali, "net", "wowsoftware", "hidemyemulator", "core", "ModuleStatus.smali"
    )
    replace_once(
        p,
        r"(\.method public final isModuleActive\(\)Z\n    \.locals 1\n\n    \.line 1\n)    const/4 v0, 0x0",
        r"\1    const/4 v0, 0x1",
        "ModuleStatus -> active",
    )


# ---- 1.4 patch set (server-side licensing: nb/s license state) ----

def patch14_mapper(smali):
    """d9/b.r() server-JSON mapper always returns lifetime premium."""
    p = os.path.join(smali, "d9", "b.smali")
    replace_once(
        p,
        r"\.method public static r\(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZoneId;\)Lnb/s;.*?\.end method",
        """.method public static r(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZoneId;)Lnb/s;
    .locals 1
    new-instance p0, Lnb/p;
    const/4 v0, 0x0
    invoke-direct {p0, v0, v0}, Lnb/p;-><init>(Ljava/lang/Long;Ljava/lang/String;)V
    return-object p0
.end method""",
        "d9/b mapper -> premium",
    )


def patch14_flow(smali):
    """ec/q license flow fallback always premium."""
    p = os.path.join(smali, "ec", "q.smali")
    replace_once(
        p,
        r"(:cond_0\n)    sget-object p1, Lnb/r;->a:Lnb/r;",
        r"""\1    new-instance p1, Lnb/p;
    const/4 v1, 0x0
    invoke-direct {p1, v1, v0}, Lnb/p;-><init>(Ljava/lang/Long;Ljava/lang/String;)V""",
        "ec/q flow -> premium",
    )



# ---- 1.5 patch set (same server licensing, re-obfuscated: ob/r premium) ----

def patch15_mapper(smali):
    """d9/a.H() server-JSON mapper always returns lifetime premium."""
    p = os.path.join(smali, "d9", "a.smali")
    replace_once(
        p,
        r"\.method public static H\(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZoneId;\)Lob/u;.*?\.end method",
        """.method public static H(Ljava/lang/String;Ljava/lang/String;Ljava/time/ZoneId;)Lob/u;
    .locals 1
    new-instance p0, Lob/r;
    const/4 v0, 0x0
    invoke-direct {p0, v0, v0}, Lob/r;-><init>(Ljava/lang/Long;Ljava/lang/String;)V
    return-object p0
.end method""",
        "d9/a mapper -> premium",
    )


def patch15_flow(smali):
    """hc/p license flow fallback always premium."""
    p = os.path.join(smali, "hc", "p.smali")
    replace_once(
        p,
        r"(:cond_0\n)    sget-object p1, Lob/t;->a:Lob/t;",
        r"""\1    new-instance p1, Lob/r;
    const/4 v1, 0x0
    invoke-direct {p1, v1, v0}, Lob/r;-><init>(Ljava/lang/Long;Ljava/lang/String;)V""",
        "hc/p flow -> premium",
    )


def patch15_unlock_calc(smali):
    p = os.path.join(smali, "kc", "p.smali")
    replace_once(
        p,
        r"    if-ne p1, v0, :cond_4",
        "    const/4 p1, 0x1\n",
        "kc/r unlock -> true",
    )


def patch15_state_flags(smali):
    p = os.path.join(smali, "kc", "q.smali")
    replace_once(
        p,
        r"    iget-boolean v2, v0, Lkc/q;->i:Z",
        "    const/4 v2, 0x1",
        "kc/q a-flag -> true",
    )
    replace_once(
        p,
        r"    iget-boolean v10, v0, Lkc/q;->m:Z",
        "    const/4 v10, 0x1",
        "kc/q i-flag -> true",
    )
    replace_once(
        p,
        r"(:cond_0\n)    const-wide v11, -0x140411d2ffffffd6L",
        r"""\1    new-instance v1, Lob/r;
    const/4 v7, 0x0
    invoke-direct {v1, v7, v7}, Lob/r;-><init>(Ljava/lang/Long;Ljava/lang/String;)V
    const-wide v11, -0x140411d2ffffffd6L""",
        "kc/q license -> premium",
    )


def patch15_initial(smali):
    p = os.path.join(smali, "kc", "r.smali")
    replace_once(
        p,
        r"    const/4 v15, 0x0",
        "    const/4 v15, 0x1",
        "kc/r i-flag -> true",
    )
    replace_once(
        p,
        r"    move v7, v3",
        "    const/4 v7, 0x1",
        "kc/r a-flag -> true",
    )
    replace_once(
        p,
        r"    sget-object v8, Lob/s;->a:Lob/s;",
        r"""    new-instance v8, Lob/r;
    const/4 v9, 0x0
    invoke-direct {v8, v9, v9}, Lob/r;-><init>(Ljava/lang/Long;Ljava/lang/String;)V""",
        "kc/r license -> premium",
    )


def patch_branding(smali, res):
    """Status text -> Premium, About credit, styled launch toast."""
    for d in ("values", "values-in"):
        p = os.path.join(res, d, "strings.xml")
        replace_once(
            p,
            r"<string name=\"app_info_not_activated\">.*?</string>",
            "<string name=\"app_info_not_activated\">Premium</string>",
            f"{d} status -> Premium",
        )
        replace_once(
            p,
            r"<string name=\"app_info_developer\">.*?</string>",
            "<string name=\"app_info_developer\">Patched by reverser.id</string>",
            f"{d} developer credit",
        )
        replace_once(
            p,
            r"<string name=\"app_info_about\">.*?</string>",
            lambda m: m.group(0).replace(
                m.group(0)[m.group(0).index(">") + 1:m.group(0).rindex("<")],
                m.group(0)[m.group(0).index(">") + 1:m.group(0).rindex("<")]
                + " · patched by reverser.id"),
            f"{d} about header credit",
        )
    p = os.path.join(
        smali, "net", "wowsoftware", "hidemyemulator", "MainActivity.smali")
    replace_once(
        p,
        r"(\.method public final onCreate\(Landroid/os/Bundle;\)V\n    \.locals 9\n\n    \.line 1\n)",
    r"""\1    new-instance v9, Landroid/widget/TextView;
    invoke-direct {v9, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    const-string v10, "\\u2726 Patched by reverser.id | https://reverser.id"
    invoke-virtual {v9, v10}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    const v10, -0x50506
    invoke-virtual {v9, v10}, Landroid/widget/TextView;->setTextColor(I)V
    const/high16 v10, 0x41600000
    const/4 v11, 0x2
    invoke-virtual {v9, v11, v10}, Landroid/widget/TextView;->setTextSize(IF)V
    const/16 v10, 0x2c
    const/16 v11, 0x18
    invoke-virtual {v9, v10, v11, v10, v11}, Landroid/widget/TextView;->setPadding(IIII)V
    new-instance v12, Landroid/graphics/drawable/GradientDrawable;
    invoke-direct {v12}, Landroid/graphics/drawable/GradientDrawable;-><init>()V
    const v10, -0xd9d9da
    invoke-virtual {v12, v10}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V
    const/high16 v10, 0x42200000
    invoke-virtual {v12, v10}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V
    const/4 v10, 0x2
    const v11, -0xa73f01
    invoke-virtual {v12, v10, v11}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V
    invoke-virtual {v9, v12}, Landroid/widget/TextView;->setBackground(Landroid/graphics/drawable/Drawable;)V
    new-instance v12, Landroid/widget/Toast;
    invoke-direct {v12, p0}, Landroid/widget/Toast;-><init>(Landroid/content/Context;)V
    invoke-virtual {v12, v9}, Landroid/widget/Toast;->setView(Landroid/view/View;)V
    const/4 v10, 0x1
    invoke-virtual {v12, v10}, Landroid/widget/Toast;->setDuration(I)V
    const/16 v10, 0x51
    const/4 v11, 0x0
    const/16 v13, 0x60
    invoke-virtual {v12, v10, v11, v13}, Landroid/widget/Toast;->setGravity(III)V
    invoke-virtual {v12}, Landroid/widget/Toast;->show()V
""",
        "launch toast (styled)",
        must_contain=["reverser.id"],
    )
    # .locals 9 -> 14 for the extra registers
    replace_once(
        p,
        r"(\.method public final onCreate\(Landroid/os/Bundle;\)V\n)    \.locals 9",
        r"\1    .locals 14",
        "toast registers",
    )


def patch14_unlock_calc(smali):
    """hc/r unlock computation always true (fixes VerifyError-safe const)."""
    p = os.path.join(smali, "hc", "r.smali")
    replace_once(
        p,
        r"    if-ne p1, v0, :cond_4",
        "    const/4 p1, 0x1\n",
        "hc/r unlock -> true",
    )


def patch14_state_flags(smali):
    """hc/s combiner: force a-flag, i-flag and license to premium."""
    p = os.path.join(smali, "hc", "s.smali")
    replace_once(
        p,
        r"    iget-boolean v2, v0, Lhc/s;->i:Z",
        "    const/4 v2, 0x1",
        "hc/s a-flag -> true",
    )
    replace_once(
        p,
        r"    iget-boolean v10, v0, Lhc/s;->m:Z",
        "    const/4 v10, 0x1",
        "hc/s i-flag -> true",
    )
    replace_once(
        p,
        r"(:cond_0\n)    const-wide v11, -0x14040da4ffffffd6L",
        r"""\1    new-instance v1, Lnb/p;
    const/4 v7, 0x0
    invoke-direct {v1, v7, v7}, Lnb/p;-><init>(Ljava/lang/Long;Ljava/lang/String;)V
    const-wide v11, -0x14040da4ffffffd6L""",
        "hc/s license -> premium",
    )


def patch14_initial(smali):
    """hc/t initial state: a-flag, i-flag and license to premium."""
    p = os.path.join(smali, "hc", "t.smali")
    replace_once(
        p,
        r"    const/4 v15, 0x0",
        "    const/4 v15, 0x1",
        "hc/t i-flag -> true",
    )
    replace_once(
        p,
        r"    move v7, v3",
        "    const/4 v7, 0x1",
        "hc/t a-flag -> true",
    )
    replace_once(
        p,
        r"    sget-object v8, Lnb/q;->a:Lnb/q;",
        r"""    new-instance v8, Lnb/p;
    const/4 v9, 0x0
    invoke-direct {v8, v9, v9}, Lnb/p;-><init>(Ljava/lang/Long;Ljava/lang/String;)V""",
        "hc/t license -> premium",
    )


def main():
    ap = argparse.ArgumentParser(
        description="HideMyEmulator 1.3/1.4/1.5 -> premium. Example: python patch.py release-1.5.apk")
    ap.add_argument("apk", nargs="?", default="release-1.3.apk",
                    help="input APK (default: release-1.3.apk)")
    ap.add_argument("--apk", dest="apk_flag", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None,
                    help="output APK (default: <apk>-premium-signed.apk)")
    ap.add_argument("--apktool", default="C:/bin/apktool/apktool.jar")
    ap.add_argument("--build-tools", default=os.path.join(
        os.environ.get("ANDROID_HOME", ""), "build-tools", "36.0.0"))
    ap.add_argument("--keystore", default=None,
                    help="signing keystore (default: ephemeral key)")
    ap.add_argument("--storepass", default="android")
    ap.add_argument("--keypass", default="android")
    ap.add_argument("--keyalias", default=None,
                    help="key alias (default: auto-detect, else 'key')")
    ap.add_argument("--no-sign", action="store_true")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()
    a.apk = a.apk_flag or a.apk
    if not os.path.isfile(a.apk):
        sys.exit(f"APK not found: {a.apk}")
    if not a.out:
        stem = os.path.splitext(os.path.basename(a.apk))[0]
        a.out = os.path.join(os.path.dirname(a.apk) or ".",
                             f"{stem}-premium-signed.apk")

    apktool = ["java", "-jar", a.apktool]
    zipalign = os.path.join(a.build_tools, "zipalign.exe")
    apksigner = os.path.join(a.build_tools, "apksigner.bat")
    java_env = {"_JAVA_OPTIONS": JAVA_OPTS}
    sign_env = {"_JAVA_OPTIONS": JAVA_SIGN_OPTS}

    work = a.workdir or tempfile.mkdtemp(prefix="hme-patch-")
    dec = os.path.join(work, "decoded")
    unsigned = os.path.join(work, "unsigned.apk")
    aligned = os.path.join(work, "aligned.apk")

    run(apktool + ["d", "-f", a.apk, "-o", dec], env_extra=java_env)
    smali = os.path.join(dec, "smali")
    with open(os.path.join(dec, "apktool.yml"), encoding="utf-8") as f:
        m = re.search(r"versionName:\s*(\S+)", f.read())
    ver = m.group(1) if m else ""
    print(f"detected version: {ver}")
    if ver.startswith("1.5"):
        patch15_mapper(smali)
        patch15_flow(smali)
        patch_module_status(smali)
        patch15_unlock_calc(smali)
        patch15_state_flags(smali)
        patch15_initial(smali)
        patch_branding(smali, os.path.join(dec, "res"))
    elif ver.startswith("1.4"):
        patch14_mapper(smali)
        patch14_flow(smali)
        patch_module_status(smali)
        patch14_unlock_calc(smali)
        patch14_state_flags(smali)
        patch14_initial(smali)
        patch_branding(smali, os.path.join(dec, "res"))
    elif ver.startswith("1.3"):
        patch_mapper(smali)
        patch_query_fallback(smali)
        patch_combine(smali)
        patch_initial(smali)
        patch_module_status(smali)
        patch_branding(smali, os.path.join(dec, "res"))
    else:
        sys.exit(f"unsupported version: {ver}")
    run(apktool + ["b", dec, "-o", unsigned], env_extra=java_env)

    if a.no_sign:
        shutil.copyfile(unsigned, a.out)
        print("unsigned ->", a.out)
        return

    run([zipalign, "-f", "4", unsigned, aligned])
    ks = a.keystore
    alias = a.keyalias
    if not ks:
        ks = os.path.join(work, "sign.keystore")
        alias = alias or "key"
        run(["keytool", "-genkeypair", "-keystore", ks, "-alias", alias,
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10950",
             "-storepass", a.storepass, "-keypass", a.keypass,
             "-dname", "CN=Patch"], env_extra=sign_env)
    elif not alias:
        # auto-detect first alias (e.g. debug keystore -> androiddebugkey)
        out = subprocess.run(
            ["keytool", "-list", "-keystore", ks,
             "-storepass", a.storepass],
            check=True, capture_output=True, text=True,
            env={**os.environ, **sign_env}).stdout
        m = re.search(r"^(\S+?),", out, re.MULTILINE)
        alias = m.group(1) if m else "key"
        print(f"using key alias: {alias}")
    run([apksigner, "sign", "--ks", ks, "--ks-key-alias", alias,
         "--ks-pass", f"pass:{a.storepass}", "--key-pass", f"pass:{a.keypass}",
         "--out", a.out, aligned], env_extra=sign_env)
    run([apksigner, "verify", a.out], env_extra=sign_env)
    print("signed ->", a.out)


if __name__ == "__main__":
    main()
