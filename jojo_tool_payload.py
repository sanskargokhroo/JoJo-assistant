"""Bound model-facing tool output without silently implying it is complete."""
import hashlib
import json

def bounded_payload(value, limit=12000):
    payload=dict(value) if isinstance(value,dict) else {'result':str(value)}
    encoded=json.dumps(payload,ensure_ascii=False,default=str)
    if len(encoded)<=limit:return payload
    # JSON escaping can expand an excerpt, so measure the final serialized object.
    result={'truncated':True,'original_chars':len(encoded),
            'sha256':hashlib.sha256(encoded.encode()).hexdigest(),
            'notice':'Partial tool result. Narrow the query or request a smaller source range before drawing conclusions about omitted content.',
            'excerpt':encoded[:limit//2]}
    if isinstance(value,dict):
        for key in ('error','status','ok'):
            if key in value:result[key]=value[key] if isinstance(value[key],(bool,int,float,type(None))) else str(value[key])[:200]
    while len(json.dumps(result,ensure_ascii=False))>limit and result['excerpt']:
        result['excerpt']=result['excerpt'][:len(result['excerpt'])//2]
    return result
