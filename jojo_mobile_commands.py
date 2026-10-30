"""Exact mobile navigation and sleep intents; never interprets sends or toggles."""
import re

def normalize(text):
    return re.sub(r'\s+',' ',re.sub(r'[,!.?।]',' ',text.casefold())).strip()

def sleep_requested(text):
    text=normalize(text)
    text=re.sub(r'^(?:theek hai|thik hai|theek|thik|okay|ok|ठीक है|अच्छा)\s*','',text)
    return text in {'off ho ja','off ho jao','off hoja','off hojao','band ho ja','band ho jao',
                    'so ja','so jao','sleep','go to sleep','stop listening','ऑफ हो जा','ऑफ हो जाओ',
                    'बंद हो जा','बंद हो जाओ','सो जाओ','चुप हो जाओ'}

ALIASES={
 'settings':('settings','setting','सेटिंग','सेटिंग्स'),
 'gallery':('gallery','album','albums','गैलरी','गैलरी ऐप','एल्बम','एलबम'),
 'messages':('sms','messages','message app','messaging','एसएमएस','मैसेज','मैसेजेस','मैसेज ऐप'),
 'contacts':('contacts','contact','कॉन्टैक्ट','कॉन्टैक्ट्स','संपर्क'),
 'dialer':('dialer','phone app','डायलर','फोन ऐप'),
 'wifi':('wifi settings','wi-fi settings','वाईफाई सेटिंग'),
 'bluetooth':('bluetooth settings','ब्लूटूथ सेटिंग'),
 'display':('display settings','डिस्प्ले सेटिंग'),
}

def navigation(text):
    text=normalize(text)
    prefixes=('','open ','launch ','show ','please open ','meri ','mera ','मेरी ','मेरा ')
    suffixes=('',' open',' kholo',' khol',' khol do',' khol de',' kholna',' open karo',' open kar',
              ' open kr',' on kr',' on karo',' खोलो',' खोल',' खोल दो',' खोल दे',' ओपन करो',' ऑन करो')
    for app,aliases in ALIASES.items():
        if any(text==prefix+alias+suffix for alias in aliases for prefix in prefixes for suffix in suffixes):
            return app
    return None

def planning_failure(exc):
    code=getattr(exc,'code',None)
    if code in (500,502,503,504) or type(exc).__name__ in ('TimeoutError','ReadTimeout'):
        return 'AI service ne time par jawab nahi diya. Yeh phone ki kharabi nahi hai. Basic apps seedhe khol sakta hoon; complex task dobara boliye.'
    if code==429:return 'AI service ki usage limit aa gayi hai. Thodi der baad try kijiye; basic app opening available hai.'
    if code in (401,403):return 'AI key ya model access mein problem hai. Laptop model settings check kijiye.'
    if type(exc).__name__ in ('JSONDecodeError','ValueError'):
        return 'AI ka action response valid nahi tha. Koi unverified action repeat nahi kiya.'
    return 'Planning complete nahi hui. Basic app opening try kar sakte hain; complex task ke liye connection aur model settings check kijiye.'
