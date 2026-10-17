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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apktool", default="C:/bin/apktool/apktool.jar")
    ap.add_argument("--build-tools", default=os.path.join(
        os.environ.get("ANDROID_HOME", ""), "build-tools", "36.0.0"))
    ap.add_argument("--keystore", default=None)
    ap.add_argument("--storepass", default="android")
    ap.add_argument("--keypass", default="android")
    ap.add_argument("--keyalias", default="key")
    ap.add_argument("--no-sign", action="store_true")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()

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
    patch_mapper(smali)
    patch_query_fallback(smali)
    patch_combine(smali)
    patch_initial(smali)
    patch_module_status(smali)
    run(apktool + ["b", dec, "-o", unsigned], env_extra=java_env)

    if a.no_sign:
        shutil.copyfile(unsigned, a.out)
        print("unsigned ->", a.out)
        return

    run([zipalign, "-f", "4", unsigned, aligned])
    ks = a.keystore
    if not ks:
        ks = os.path.join(work, "sign.keystore")
        run(["keytool", "-genkeypair", "-keystore", ks, "-alias", a.keyalias,
             "-keyalg", "RSA", "-keysize", "2048", "-validity", "10950",
             "-storepass", a.storepass, "-keypass", a.keypass,
             "-dname", "CN=Patch"], env_extra=sign_env)
    run([apksigner, "sign", "--ks", ks, "--ks-key-alias", a.keyalias,
         "--ks-pass", f"pass:{a.storepass}", "--key-pass", f"pass:{a.keypass}",
         "--out", a.out, aligned], env_extra=sign_env)
    run([apksigner, "verify", a.out], env_extra=sign_env)
    print("signed ->", a.out)


if __name__ == "__main__":
    main()
