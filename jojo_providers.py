"""OpenAI Responses / Anthropic Messages adapters for JoJo's explicit tool loop.

No provider-switch fallback: credentials are sent only to the selected vendor.
"""
import base64
import io
import json
from types import SimpleNamespace
import urllib.request
import urllib.error
from google.genai import types

class ProviderError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(f'Model provider HTTP {code}. Check your key, model access and quota.')

def contents_list(value):
    if isinstance(value,str):return [types.Content(role='user',parts=[types.Part.from_text(text=value)])]
    if isinstance(value,types.Content):return [value]
    values=value if isinstance(value,list) else [value]
    if all(isinstance(v,types.Content) for v in values):return values
    parts=[]
    for item in values:
        if isinstance(item,str):parts.append(types.Part.from_text(text=item))
        elif isinstance(item,types.Part):parts.append(item)
        elif isinstance(item,dict):parts.append(types.Part(**item))
        elif hasattr(item,'save'):
            buffer=io.BytesIO();item.save(buffer,format='PNG');parts.append(types.Part.from_bytes(data=buffer.getvalue(),mime_type='image/png'))
        else:raise ValueError('Unsupported model input type')
    return [types.Content(role='user',parts=parts)]

def declarations(tools):
    result=[]
    for tool in tools or []:
        if callable(tool):items=[types.FunctionDeclaration.from_callable_with_api_option(callable=tool,use_json_schema=True)]
        else:items=tool.function_declarations or []
        for fn in items:
            schema=fn.parameters_json_schema or (fn.parameters.model_dump(mode='json',exclude_none=True) if fn.parameters else {'type':'object','properties':{}})
            def normalize(value):
                if isinstance(value,dict):return {k:(v.lower() if k=='type' and isinstance(v,str) else normalize(v)) for k,v in value.items() if k!='propertyOrdering'}
                if isinstance(value,list):return [normalize(v) for v in value]
                return value
            result.append({'name':fn.name,'description':fn.description or '', 'parameters':normalize(schema)})
    return result

class Chat:
    def __init__(self,client,model,config,history=None):self.client,self.model,self.config,self.history=client,model,config,list(history or [])
    def send_message(self,value):
        self.history.extend(contents_list(value))
        result=self.client.generate_content(model=self.model,contents=self.history,config=self.config)
        self.history.append(result.candidates[0].content)
        return result

class ProviderClient:
    def __init__(self,provider,key):
        if provider not in ('openai','anthropic'):raise ValueError('Unsupported provider')
        self.provider,self.key=provider,key
        self.models=self
        self.chats=SimpleNamespace(create=lambda **kw:Chat(self,**kw))
        self.raw_turns={}
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):self.raw_turns.clear()
    def get(self,model):
        # Metadata checks do not imply tool/vision support for every model.
        import urllib.parse
        return SimpleNamespace(name=model,**self._request('/models/'+urllib.parse.quote(model,safe=''),None))
    def embed_content(self,**kwargs):raise RuntimeError('Semantic embeddings currently require Gemini; local journal recall remains available.')
    def _request(self,path,body):
        base='https://api.openai.com/v1' if self.provider=='openai' else 'https://api.anthropic.com/v1'
        headers={'Content-Type':'application/json'}
        if self.provider=='openai':headers['Authorization']='Bearer '+self.key
        else:headers.update({'x-api-key':self.key,'anthropic-version':'2023-06-01'})
        request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as exc:raise ProviderError(exc.code) from None
        except urllib.error.URLError:raise ConnectionError('Selected model provider is unavailable.') from None
    def generate_content(self,model,contents,config=None):
        config=config or types.GenerateContentConfig()
        if isinstance(config,dict):config=types.GenerateContentConfig(**config)
        prompt=config.system_instruction or ''
        if not isinstance(prompt,str):prompt='\n'.join(p.text or '' for p in prompt.parts)
        if config.response_mime_type=='application/json':prompt+='\nReturn only valid JSON. No markdown fences.'
        functions=declarations(config.tools)
        messages=[]
        for content in contents_list(contents):
            if id(content) in self.raw_turns:
                messages.extend(self.raw_turns[id(content)][1]);continue
            role='assistant' if content.role=='model' else 'user'
            blocks=[]
            for part in content.parts or []:
                if part.text:blocks.append({'type':('output_text' if role=='assistant' else 'input_text') if self.provider=='openai' else 'text','text':part.text})
                elif part.inline_data:
                    data=base64.b64encode(part.inline_data.data).decode();mime=part.inline_data.mime_type
                    blocks.append({'type':'input_image','image_url':f'data:{mime};base64,{data}'} if self.provider=='openai' else {'type':'image','source':{'type':'base64','media_type':mime,'data':data}})
                elif part.function_response:
                    response=part.function_response
                    if self.provider=='openai':messages.append({'type':'function_call_output','call_id':response.id,'output':json.dumps(response.response)})
                    else:blocks.append({'type':'tool_result','tool_use_id':response.id,'content':json.dumps(response.response),'is_error':bool(response.response.get('error'))})
                elif part.function_call:
                    call=part.function_call
                    if self.provider=='openai':messages.append({'type':'function_call','call_id':call.id,'name':call.name,'arguments':json.dumps(call.args)})
                    else:blocks.append({'type':'tool_use','id':call.id,'name':call.name,'input':dict(call.args or {})})
            if blocks:messages.append({'role':role,'content':blocks})
        if self.provider=='openai':
            body={'model':model,'instructions':prompt,'input':messages,'store':False,'include':['reasoning.encrypted_content']}
            if functions:body['tools']=[dict(type='function',strict=False,**fn) for fn in functions]
            if config.max_output_tokens:body['max_output_tokens']=config.max_output_tokens
            raw=self._request('/responses',body)
            if raw.get('status') not in (None,'completed'):raise RuntimeError('Model response was incomplete; no tools executed.')
            output=raw.get('output',[]);parts=[]
            for item in output:
                if item['type']=='function_call':parts.append(types.Part(function_call=types.FunctionCall(id=item['call_id'],name=item['name'],args=json.loads(item['arguments']))))
                elif item['type']=='message':
                    parts.extend(types.Part.from_text(text=b['text']) for b in item.get('content',[]) if b.get('type')=='output_text')
            preserved=output
        else:
            body={'model':model,'system':prompt,'messages':messages,'max_tokens':config.max_output_tokens or 4096}
            if functions:body['tools']=[{'name':f['name'],'description':f['description'],'input_schema':f['parameters']} for f in functions]
            raw=self._request('/messages',body)
            if raw.get('stop_reason')=='max_tokens':raise RuntimeError('Model response truncated; no tools executed.')
            output=raw.get('content',[]);parts=[]
            for item in output:
                if item['type']=='tool_use':parts.append(types.Part(function_call=types.FunctionCall(id=item['id'],name=item['name'],args=item['input'])))
                elif item['type']=='text':parts.append(types.Part.from_text(text=item['text']))
            preserved=[{'role':'assistant','content':output}]
        content=types.Content(role='model',parts=parts)
        self.raw_turns[id(content)]=(content,preserved)
        return SimpleNamespace(text='\n'.join(p.text for p in parts if p.text),candidates=[SimpleNamespace(content=content)])
