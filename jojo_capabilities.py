"""User-controlled built-in skills. Blocked executable plugins cannot be enabled."""
from jojo_config import read_preferences, save_preferences

CATALOG={
 'desktop':('Desktop control','Read screens and operate allowed desktop apps.'),
 'mobile':('Android companion','Read and operate the paired phone; USB/backend required.'),
 'web':('Web & research','Search, read pages, weather and research.'),
 'files':('Files & documents','Read/write local documents and list directories.'),
 'memory':('Memory tools','Save workflow instructions and recall learned facts.'),
 'security':('Defensive checks','Inspect links/files and run local security checks.'),
 'smart_home':('Home Assistant','Only configured, allowlisted devices.'),
}
GROUPS={
 'smart_home':{'list_smart_devices','control_smart_device'},
 'security':{'audit_device_security','inspect_link','inspect_app_file','wifi_security_guidance'},
 'memory':{'remember_workflow','search_semantic_memories','save_semantic_fact'},
 'files':{'read_local_file','write_local_file','append_to_file','list_local_directory','search_local_files','extract_pdf_text','deduplicate_and_organize_files'},
 'web':{'search_the_web','read_webpage_content','research_deep_topic','get_morning_briefing','check_live_weather'},
}
def enabled(group):return read_preferences().get('capabilities',{}).get(group,True)
def allowed_tool(name):
    group=next((group for group,names in GROUPS.items() if name in names),'desktop')
    return enabled(group) and read_preferences().get('capabilities',{}).get('tool:'+name,True)
def update(values):
    from jojo_agi.jojo_tools_registry import get_all_tools
    valid=set(CATALOG)|{'tool:'+tool.__name__ for tool in get_all_tools(include_disabled=True)}
    if set(values)-valid or any(type(v) is not bool for v in values.values()):raise ValueError('Unknown skill or invalid switch')
    current=read_preferences().get('capabilities',{});current.update(values);save_preferences({'capabilities':current})
def catalog():
    return [{'id':key,'name':value[0],'description':value[1],'enabled':enabled(key)} for key,value in CATALOG.items()]

def tool_catalog():
    from jojo_agi.jojo_tools_registry import get_all_tools
    flags=read_preferences().get('capabilities',{})
    return [{'id':'tool:'+tool.__name__,'name':tool.__name__.replace('_',' '),
             'description':(tool.__doc__ or '').strip().split('\n')[0],
             'enabled':flags.get('tool:'+tool.__name__,True)} for tool in get_all_tools(include_disabled=True)]
