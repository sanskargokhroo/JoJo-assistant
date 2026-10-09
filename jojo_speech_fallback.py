"""Offline speech helper, isolated so a stuck SAPI engine cannot freeze JoJo."""
import sys

def main():
    import pyttsx3
    text = sys.stdin.buffer.read().decode('utf-8')
    if not text:
        return
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    hindi = next((v for v in voices if any(name in v.name.lower() for name in ('hindi', 'hemant', 'kalpana'))), None)
    if hindi:
        engine.setProperty('voice', hindi.id)
    engine.setProperty('rate', 165)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

if __name__ == '__main__':
    main()
