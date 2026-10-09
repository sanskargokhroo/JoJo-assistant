"""Offline debug APK build using installed Android SDK tools; no Gradle daemon."""
from pathlib import Path
import os
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
SDK = Path(os.environ.get('ANDROID_HOME', Path.home() / 'AppData/Local/Android/Sdk'))
JAVA = Path(os.environ.get('JAVA_HOME', 'C:/Program Files/Java/jdk-20')) / 'bin'
TOOLS = SDK / 'build-tools/35.0.0'
ANDROID = SDK / 'platforms/android-35/android.jar'
OUT = ROOT / 'app/build/local'
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'classes').mkdir(exist_ok=True)
(OUT / 'dex').mkdir(exist_ok=True)

def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)

run(TOOLS/'aapt2.exe', 'compile', '--dir', ROOT/'app/src/main/res', '-o', OUT/'resources.zip')
manifest = (ROOT/'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8').replace('<manifest ', '<manifest package="app.jojo.nativevoice" ', 1)
(OUT/'AndroidManifest.xml').write_text(manifest, encoding='utf-8')
run(TOOLS/'aapt2.exe', 'link', '-o', OUT/'base.apk', '--manifest', OUT/'AndroidManifest.xml',
    '-I', ANDROID, '--min-sdk-version', '30', '--target-sdk-version', '35', '--version-code', '1', '--version-name', '0.1.0', OUT/'resources.zip')
sources = sorted((ROOT/'app/src/main/java').rglob('*.java'))
run(JAVA/'javac.exe','-encoding','UTF-8','-source','17','-target','17','-classpath',ANDROID,'-d',OUT/'classes',*sources)
run(JAVA/'jar.exe','cf',OUT/'classes.jar','-C',OUT/'classes','.')
run(JAVA/'java.exe','-cp',TOOLS/'lib/d8.jar','com.android.tools.r8.D8','--lib',ANDROID,'--min-api','30','--output',OUT/'dex',OUT/'classes.jar')
with zipfile.ZipFile(OUT/'base.apk','a') as apk:
    for dex in (OUT/'dex').glob('*.dex'): apk.write(dex, dex.name)
run(TOOLS/'zipalign.exe','-f','4',OUT/'base.apk',OUT/'aligned.apk')
keystore=OUT/'debug.keystore'
if not keystore.exists():
    run(JAVA/'keytool.exe','-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','androiddebugkey',
        '-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=JoJo Local Debug')
target=OUT/'JoJo-debug.apk'
run(JAVA/'java.exe','-jar',TOOLS/'lib/apksigner.jar','sign','--ks',keystore,'--ks-pass','pass:android','--out',target,OUT/'aligned.apk')
run(JAVA/'java.exe','-jar',TOOLS/'lib/apksigner.jar','verify','--verbose',target)
print('APK:',target)
