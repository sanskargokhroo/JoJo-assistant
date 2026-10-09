"""Owner-scoped read → offer → recipient → dictated reply conversation."""
import re
import unicodedata

def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', str(text)).casefold().split()).strip(' .!?।')

def read_mode(text):
    value=norm(text)
    reading=bool(re.search(r'\b(unread|un read|new|read|check|aay[ai]|aaye|kis|kiski|kiska|kaun|bata|btaa|pad[h]?)\b|किस|कौन|आया|आए|आई|पढ़|पढ|बताओ|अनरीड|नया|नई',value))
    if not reading:return ''
    if re.search(r'\b(call|calls|missed)\b|कॉल|मिस्ड',value):return 'calls'
    if re.search(r'whatsapp|व्हाट्स|वॉट्स',value):return 'whatsapp'
    if re.search(r'\b(msg|message|messages|sms|chat|chats)\b|मैसेज|संदेश|चैट',value):return 'messages'
    return ''

def decision(text):
    value=norm(text)
    if value in {'yes','haan','haa','ha','haan ji','yes please','haan karo','haan kr do','haan kar do','हाँ','हां','हाँ जी','हां जी','हाँ करो','हां करो'}:return 'yes'
    if value in {'no','na','naa','nahi','nahin','nhi','no reply','nahi karna','nahi rehne do','nahi band kar do','नहीं','ना','नही','नहीं करना','नहीं रहने दो','नहीं बंद कर दो'}:return 'no'
    return ''

def direct_reply(text):
    match=re.match(r'(?is)^\s*(?:(?:usko|isko|use|usse|उसे|उसको|इसको)\s+)?(?:ye\s+|यह\s+)?(?:reply|jawab|जवाब|रिप्लाई)\s*(?:(?:kar|kr|karo|do|de|कर|करो|दो|दे)\s*)*[:,-]?\s*(.+)$',text)
    return match.group(1).strip() if match else ''

def report_items(items, observations):
    """Only speak quoted sender/text observed together on a permitted app screen."""
    if not isinstance(items,list) or not 1<=len(items)<=20:
        raise ValueError('Readable message/call details verify nahi hue. Screen par aur check karna hoga.')
    verified=[]
    for item in items:
        if not isinstance(item,dict):raise ValueError('Invalid inbox result')
        sender=str(item.get('sender','')).strip();body=str(item.get('text','')).strip()
        if not sender or not body or len(sender)>160 or len(body)>2000:
            raise ValueError('Sender/message details incomplete hain.')
        if not any(norm(sender) in norm(screen) and norm(body) in norm(screen) for screen in observations):
            raise ValueError('Message/caller ko observed screen se verify nahi kar paya; guess nahi karunga.')
        entry={'sender':sender,'text':body}
        if entry not in verified:verified.append(entry)
    return verified

def offer(items, mode):
    senders=list(dict.fromkeys(item['sender'] for item in items))
    return {'phase':'offer','recipients':senders,'mode':mode,'recipient':''}

def empty_report(evidence, observations):
    if not isinstance(evidence,str) or not evidence.strip():return ''
    if not re.search(r'no (unread|new|recent|missed)|all caught up|कोई.*(नहीं|नही)',norm(evidence)):return ''
    if not any(norm(evidence) in norm(screen) for screen in observations):return ''
    return 'Check ki gayi current view par: '+evidence+'. Baaki chats/history ka complete check claim nahi kar raha.'

def advance(pending, utterance):
    """Returns next state + prompt, close request or exact authorized message."""
    pending=dict(pending);answer=decision(utterance)
    if answer=='no':return None,{'close':True}
    phase=pending['phase']
    if phase=='offer':
        body=direct_reply(utterance)
        if answer!='yes' and not body:
            return None,{'new_command':True}
        if len(pending['recipients'])!=1:
            pending.update(phase='recipient',body=body)
            return pending,{'reply':'Kisko reply karna hai? '+', '.join(pending['recipients'])}
        pending['recipient']=pending['recipients'][0]
        if body:return None,{'send':body,'recipient':pending['recipient'],'mode':pending['mode']}
        pending['phase']='body'
        return pending,{'reply':pending['recipient']+' ko kya reply karna hai, sir?'}
    if phase=='recipient':
        value=norm(utterance)
        matches=[name for name in pending['recipients'] if value in {norm(name),norm(name)+' ko',norm(name)+' को'}]
        if len(matches)!=1:return pending,{'reply':'Exact naam boliye: '+', '.join(pending['recipients'])}
        pending['recipient']=matches[0]
        if pending.get('body'):return None,{'send':pending['body'],'recipient':matches[0],'mode':pending['mode']}
        pending['phase']='body'
        return pending,{'reply':matches[0]+' ko kya reply karna hai, sir?'}
    if phase=='body':
        if answer=='yes' or not utterance.strip():return pending,{'reply':'Message ka exact text boliye, sir.'}
        return None,{'send':direct_reply(utterance) or utterance.strip(),'recipient':pending['recipient'],'mode':pending['mode']}
    return None,{'new_command':True}

def read_action_allowed(action, screen, mode):
    kind=action['type']
    if kind=='type':
        line=next((line for line in screen.splitlines() if line.startswith(str(action.get('node'))+': ')),'')
        return bool(re.search(r'search|खोज|ढूंढ',line,re.I))
    if kind!='click':return True
    line=next((line for line in screen.splitlines() if line.startswith(str(action.get('node'))+': ')),'')
    label=re.sub(r'^\d+:\s*','',line).split(' clickable=')[0].strip()
    if mode=='calls':
        return norm(label) in {'calls','recents','recent','missed','all','history','call history','हाल ही के','मिस्ड'}
    return not re.search(r'\b(send|reply|call|video call|voice call|delete|archive|forward)\b|भेज|जवाब|कॉल|डिलीट',label,re.I)
