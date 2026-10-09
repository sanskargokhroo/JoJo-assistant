"""Deterministic summaries of opt-in phone notifications; no inbox completeness claim."""
import json
import re
from jojo_policy import blocked_reason

def notification_intent(text):
    return bool(re.fullmatch(r'(?:jojo\s+)?(?:read |show |summarize |meri |mere )?(?:new |recent )?(?:notifications?|नोटिफिकेशन)(?:\s+(?:read karo|batao|btaa|dikhao|padho|summary|पढ़ो|बताओ))?[ .!?।]*',text.strip(),re.I))

def summarize_notifications(raw):
    if not raw:return 'Phone par notification summaries enable kijiye aur JoJo notification access allow kijiye.'
    try:items=json.loads(raw)
    except (ValueError,TypeError):return 'Notification data read nahi hua; dobara try kijiye.'
    if not isinstance(items,list):return 'Notification data valid nahi hai.'
    lines=[];seen=set()
    for item in items[-40:]:
        if not isinstance(item,dict):continue
        package=str(item.get('package',''));title=str(item.get('title',''))[:150];body=str(item.get('text',''))[:700]
        if not package or blocked_reason(package) or re.search(r'\botp\b|password|passcode|verification.code|security.code|\bpin\b|payment|upi|cvv',title+' '+body,re.I):continue
        key=(package,title,body)
        if key in seen:continue
        seen.add(key);lines.append(f'{package} — {title}: {body}')
    return ('Available notification previews (complete inbox/unread count nahi):\n'+'\n'.join(lines[-10:])) if lines else 'Allowed notification buffer mein readable previews nahi hain. Iska matlab zero unread messages nahi hai.'
