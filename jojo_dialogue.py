"""Natural short acknowledgements and speech-only text cleanup."""
import random
import re
import unicodedata
_last_greeting = None

def wake_reply():
    global _last_greeting
    choices = ['Haan, bolo—kya karna hai?', 'Sun raha hoon. Batao.', 'Ji, kya karein?', 'Bolo, aaj kya plan hai?']
    choices = [s for s in choices if s != _last_greeting]
    _last_greeting = random.choice(choices)
    return _last_greeting

def speech_text(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', str(text))
    text = re.sub(r'https?://\S+', '', text)
    # Remove pictographs, flags, emoji modifiers and keycap/variation glue;
    # keep Hindi vowel signs and normal punctuation/numbers.
    text = ''.join(c for c in text if not (
        0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF
        or ord(c) in (0xFE0F, 0xFE0E, 0x200D, 0x20E3)
        or unicodedata.category(c) == 'So'))
    text = re.sub(r'[`*#_]+', '', text)
    return re.sub(r'\s+', ' ', text).strip()
