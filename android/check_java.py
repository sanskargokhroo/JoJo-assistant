"""Compile native Java for validation only. Never packages, signs or generates an APK."""
import argparse
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk',default=os.environ.get('ANDROID_HOME',str(Path.home()/'AppData/Local/Android/Sdk')))
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    android=Path(args.sdk)/'platforms/android-35/android.jar'
    javac=Path(os.environ.get('JAVA_HOME','C:/Program Files/Java/jdk-20'))/'bin/javac.exe'
    out=root/'app/build/java-check';out.mkdir(parents=True,exist_ok=True)
    ET.parse(root/'app/src/main/AndroidManifest.xml')
    sources=sorted((root/'app/src/main/java').rglob('*.java'))
    subprocess.run([str(javac),'-encoding','UTF-8','-source','17','-target','17','-classpath',str(android),'-d',str(out),*[str(s) for s in sources]],check=True)
    print('PASS: native Java compile + manifest XML parse. No APK generated.')

if __name__=='__main__':main()
