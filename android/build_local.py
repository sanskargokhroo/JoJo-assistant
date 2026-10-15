"""Offline debug APK build using installed Android SDK tools; no Gradle daemon."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
SDK = Path(os.environ.get('ANDROID_HOME', Path.home() / 'AppData/Local/Android/Sdk'))
JAVA = Path(os.environ.get('JAVA_HOME', 'C:/Program Files/Java/jdk-20')) / 'bin'
TOOLS = SDK / 'build-tools/35.0.0'
ANDROID = SDK / 'platforms/android-35/android.jar'
OUT = ROOT / 'app/build/local'
OUT.mkdir(parents=True, exist_ok=True)

def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)

gradle = (ROOT/'app/build.gradle').read_text(encoding='utf-8')
version_code = re.search(r'versionCode\s+(\d+)', gradle).group(1)
version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)

# Fresh intermediates prevent deleted Java classes leaking into the new APK.
# Preserve the signing key and replace the old APK only after verification.
with tempfile.TemporaryDirectory(prefix='jojo-build-', dir=OUT) as temporary:
    work = Path(temporary)
    (work/'classes').mkdir()
    (work/'dex').mkdir()
    run(TOOLS/'aapt2.exe', 'compile', '--dir', ROOT/'app/src/main/res', '-o', work/'resources.zip')
    manifest = (ROOT/'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8').replace('<manifest ', '<manifest package="app.jojo.nativevoice" ', 1)
    (work/'AndroidManifest.xml').write_text(manifest, encoding='utf-8')
    run(TOOLS/'aapt2.exe', 'link', '-o', work/'base.apk', '--manifest', work/'AndroidManifest.xml',
        '-I', ANDROID, '--min-sdk-version', '30', '--target-sdk-version', '35', '--version-code', version_code, '--version-name', version_name, work/'resources.zip')
    sources = sorted((ROOT/'app/src/main/java').rglob('*.java'))
    run(JAVA/'javac.exe','-encoding','UTF-8','-source','17','-target','17','-classpath',ANDROID,'-d',work/'classes',*sources)
    run(JAVA/'jar.exe','cf',work/'classes.jar','-C',work/'classes','.')
    run(JAVA/'java.exe','-cp',TOOLS/'lib/d8.jar','com.android.tools.r8.D8','--lib',ANDROID,'--min-api','30','--output',work/'dex',work/'classes.jar')
    with zipfile.ZipFile(work/'base.apk','a') as apk:
        for dex in (work/'dex').glob('*.dex'): apk.write(dex, dex.name)
    run(TOOLS/'zipalign.exe','-f','4',work/'base.apk',work/'aligned.apk')
    keystore=OUT/'debug.keystore'
    if not keystore.exists():
        run(JAVA/'keytool.exe','-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','androiddebugkey',
            '-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=JoJo Local Debug')
    target=work/'JoJo-debug.apk'
    run(JAVA/'java.exe','-jar',TOOLS/'lib/apksigner.jar','sign','--ks',keystore,'--ks-pass','pass:android','--out',target,work/'aligned.apk')
    run(JAVA/'java.exe','-jar',TOOLS/'lib/apksigner.jar','verify','--verbose',target)
    run(TOOLS/'zipalign.exe','-c','4',target)
    target.replace(OUT/'JoJo-debug.apk')
print('APK:',OUT/'JoJo-debug.apk')
