"""Run the phone's speech sanitizer on a host JDK without building an APK."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class AndroidSpeechTests(unittest.TestCase):
    def test_spoken_text_preserves_words_and_removes_emoji(self):
        home = Path(os.environ.get('JAVA_HOME', 'C:/Program Files/Java/jdk-20'))
        javac = shutil.which('javac') or str(home / 'bin/javac.exe')
        java = shutil.which('java') or str(home / 'bin/java.exe')
        if not Path(javac).is_file() or not Path(java).is_file():
            self.skipTest('Host JDK not installed')
        source = Path(__file__).resolve().parents[1] / 'android/app/src/main/java/app/jojo/nativevoice/JojoSpeechText.java'
        harness = '''package app.jojo.nativevoice;
public class JojoSpeechCheck {
    static void check(String input,String expected){
        String actual=JojoSpeechText.clean(input);
        if(!actual.equals(expected))throw new AssertionError(actual+" != "+expected);
    }
    public static void main(String[] args){
        check("हाँ 😂 बॉस 👨‍💻 12:30 बजे 👍🏽", "हाँ बॉस 12:30 बजे");
        check("**जींस** ₹500 ✅", "जींस ₹500");
        check("[Amazon](https://example.com) खोलो https://example.com", "Amazon खोलो");
        check("😂👍🏽", ""); check(null, "");
    }
}'''
        with tempfile.TemporaryDirectory(prefix='jojo-java-test-') as directory:
            test = Path(directory) / 'JojoSpeechCheck.java'
            test.write_text(harness, encoding='utf-8')
            subprocess.run([javac, '-encoding', 'UTF-8', '-d', directory, str(source), str(test)], check=True, capture_output=True)
            subprocess.run([java, '-cp', directory, 'app.jojo.nativevoice.JojoSpeechCheck'], check=True, capture_output=True)
