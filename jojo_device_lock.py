"""Desktop lock and routing. Android saved-PIN unlock is handled only by its native vault."""
import re
import ctypes

UNLOCK_REPLY='PIN/fingerprint/Windows Hello se khud unlock kijiye. JoJo lock bypass ya aapki jagah biometric authentication nahi kar sakta. Unlock ke baad JoJo bolkar task resume kijiye.'

def lock_intent(text, source):
    value=text.casefold().strip(' .!?।')
    if re.search(r'\b(why|how|explain|nahi|not|mat|dont)\b|कैसे|क्यों|मत|नहीं',value):return None
    unlock=bool(re.search(r'\bunlock\b|अनलॉक',value))
    lock=bool(re.search(r'\block\b|लॉक',value))
    if not (unlock or lock):return None
    if len(value)>100:return None
    words=re.sub(r'अनलॉक','unlock',value)
    words=re.sub(r'लॉक','lock',words)
    allowed={'jojo','please','lock','unlock','the','my','this','phone','mobile','android','laptop','pc','computer','desktop','screen','device',
             'mera','meri','mere','isko','karo','kar','kr','do','de','boss','sir','फोन','फ़ोन','मोबाइल','लैपटॉप','कंप्यूटर','स्क्रीन','को','कर','करो','दो','मेरा','मेरे','whatsapp','app','व्हाट्सएप'}
    if any(word not in allowed for word in words.split()):return None
    if re.search(r'whatsapp|app|व्हाट्स',value):return ('unlock','app') if unlock else None
    target='mobile' if re.search(r'\b(phone|mobile|android)\b|फोन|फ़ोन|मोबाइल',value) else 'laptop' if re.search(r'\b(laptop|pc|computer|desktop)\b|लैपटॉप|कंप्यूटर',value) else source
    return ('unlock' if unlock else 'lock',target)

def request_windows_lock():
    accepted=bool(ctypes.windll.user32.LockWorkStation())
    return 'Windows ko lock request bhej diya; actual lock screen verify kijiye.' if accepted else 'Windows ne lock request accept nahi ki. Win+L se manually lock kijiye.'

def desktop_command(text,source='laptop'):
    intent=lock_intent(text,source)
    if not intent:return None
    action,target=intent
    if action=='unlock':return UNLOCK_REPLY
    if target!='laptop':return 'Phone lock karne ke liye phone ke native JoJo mein command boliye. Laptop ko lock nahi kiya.'
    return request_windows_lock()
