"""Conservative direct routes for single shopping navigation commands."""
import re
from urllib.parse import quote

def shopping_navigation(text):
    value = text.casefold().strip(' .!?')
    if re.search(r'\b(buy|pay|checkout|order|compare|cheapest|best|review|select|cart|login|download)\b|खरीद|भुगतान', value):
        return None
    if re.search(r'\b(then|phir|fir|uske baad|notepad|youtube|send|message)\b|फिर',value):
        return None
    if re.search(r'\b(google|youtube|bing|delete|save|send)\b',value):
        return None
    if re.search(r'amazon|अमेज़न',value) and re.search(r'flipkart|फ्लिपकार्ट',value):
        return None
    shop = 'Flipkart' if re.search(r'flipkart|फ्लिपकार्ट',value) else 'Amazon'
    if not re.search(r'amazon|अमेज़न|अमेजन|flipkart|फ्लिपकार्ट|\bjeans\b|जींस',value):
        return None
    if not re.search(r'\b(open|kholo|khol|search|dhundo|dikhao|dikha)\b|खोल|सर्च|ढूंढ|दिखा',value):
        return None
    phrases = ['new tab','nayi tab','nai tab','naye tab','नए टैब','नयी टैब','नई टैब',
               'google chrome','amazon.in','amazon','अमेज़न','अमेजन','flipkart','फ्लिपकार्ट','chrome','क्रोम',
               'search','open','kholo','khol','karke','krke','kar','karo','kr','do','de','please',
               'dhundo','dikhao','dikha','jojo','par','per','pe','mein','mai','me','in','on','a','the','for','aur','and',
               'खोलो','खोल','सर्च','करो','कर','दो','पर','में','और','जोजो','दिखाओ']
    pattern = r'(?<!\w)(?:'+'|'.join(re.escape(p) for p in sorted(phrases,key=len,reverse=True))+r')(?!\w)'
    query = re.sub(r'\s+',' ',re.sub(pattern,' ',value)).strip(' ,')
    if re.search(r'\b(tab|window|click|type|save|usme|usmein)\b',query):
        return None
    base='https://www.flipkart.com' if shop=='Flipkart' else 'https://www.amazon.in'
    url=base+(('/search?q=' if shop=='Flipkart' else '/s?k=')+quote(query) if query else '')
    return shop,query,url
