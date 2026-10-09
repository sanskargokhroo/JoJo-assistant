import unittest
from unittest.mock import Mock
from google.genai import types
from jojo_providers import ProviderClient,declarations

def multiply(a:int,b:int)->int:
    """Multiply two integers."""
    return a*b

class ProvidersTests(unittest.TestCase):
    def test_callable_schema_and_response_tool_roundtrip(self):
        client=ProviderClient('openai','fixture-key')
        call={'type':'function_call','id':'fc_1','call_id':'call_1','name':'multiply','arguments':'{"a":6,"b":7}'}
        reasoning={'type':'reasoning','id':'rs_1','summary':[],'encrypted_content':'opaque-fixture'}
        client._request=Mock(side_effect=[{'status':'completed','output':[reasoning,call]}, {'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'42'}]}]}])
        config=types.GenerateContentConfig(tools=[multiply])
        first=types.Content(role='user',parts=[types.Part.from_text(text='6 times 7')])
        response=client.generate_content(model='fixture-model',contents=[first],config=config)
        follow=types.Content(role='user',parts=[types.Part(function_response=types.FunctionResponse(id='call_1',name='multiply',response={'result':42}))])
        final=client.generate_content(model='fixture-model',contents=[first,response.candidates[0].content,follow],config=config)
        body=client._request.call_args.args[1]
        self.assertFalse(body['store']);self.assertIn(reasoning,body['input'])
        self.assertEqual(body['input'][-1]['call_id'],'call_1');self.assertEqual(final.text,'42')
        self.assertEqual(body['tools'][0]['parameters']['properties']['a']['type'],'integer')
    def test_anthropic_tools_and_images(self):
        client=ProviderClient('anthropic','fixture-key')
        client._request=Mock(return_value={'stop_reason':'tool_use','content':[{'type':'tool_use','id':'t1','name':'multiply','input':{'a':2,'b':3}}]})
        response=client.generate_content(model='fixture-model',contents=[types.Part.from_bytes(data=b'fixture',mime_type='image/png'),'Read image'],config=types.GenerateContentConfig(tools=[multiply]))
        follow=types.Content(role='user',parts=[types.Part(function_response=types.FunctionResponse(id='t1',name='multiply',response={'result':6}))])
        client.generate_content(model='fixture-model',contents=[response.candidates[0].content,follow])
        messages=client._request.call_args.args[1]['messages']
        self.assertEqual(messages[-1]['content'][0]['tool_use_id'],'t1')
        first=client._request.call_args_list[0].args[1]
        self.assertEqual(first['messages'][0]['content'][0]['type'],'image')
    def test_truncation_does_not_return_actions(self):
        for provider,raw in [('openai',{'status':'incomplete'}),('anthropic',{'stop_reason':'max_tokens'})]:
            client=ProviderClient(provider,'fixture');client._request=Mock(return_value=raw)
            with self.assertRaises(RuntimeError):client.generate_content(model='fixture',contents='hello')
    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):ProviderClient('untrusted-proxy','fixture')

if __name__=='__main__':unittest.main()
