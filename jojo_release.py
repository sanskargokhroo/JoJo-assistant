"""Audit/export a source-only JoJo snapshot. Never copies private state or Git history."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parent
PRIVATE_NAMES={'firebase_key.json','jojo_account.json','jojo_owner_identity.json','boss_voice_profile.npy',
               'jojo_memory.db','jojo_owner_voice.npz','android_pairing.json','.env'}
def files(root=ROOT):
    chosen={root/name for name in ('README.md','requirements.txt','.gitignore','.env.example','start.py','LICENSE','SECURITY.md','CONTRIBUTING.md') if (root/name).is_file()}
    for pattern in ('jojo_*.py','jojo_*.bat','jojo_*.vbs','jojo_*.ps1','jojo_*.sh','start_jojo*.bat','JOJO_*.md','JOJO_RELEASE_METADATA.json'):
        chosen.update(root.glob(pattern))
    for folder in ('jojo_agi','jojo_skills','tests'):
        chosen.update((root/folder).glob('*.py'))
    for folder in ('assets','.github'):
        if (root/folder).exists():chosen.update(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.svg','.md','.yml','.yaml','.json'))
    for name in ('README.md','build.gradle','settings.gradle','build_local.py','check_java.py','install_on_phone.ps1','app/build.gradle'):
        if (root/'android'/name).is_file():chosen.add(root/'android'/name)
    chosen.update(p for p in (root/'android/app/src').rglob('*') if p.is_file() and p.suffix in ('.java','.xml'))
    chosen.update(p for p in (root/'web').glob('*') if p.is_file() and p.suffix in ('.html','.js','.json','.glb'))
    chosen.update((root/'web/icons').glob('jojo_*.png'))
    return sorted(chosen)

def audit(selected,root=ROOT):
    issues=[]
    metadata_path=root/'JOJO_RELEASE_METADATA.json'
    public_developer=json.loads(metadata_path.read_text(encoding='utf-8')).get('developer','') if metadata_path.is_file() else ''
    patterns=[('Google API key',re.compile(r'AIza[0-9A-Za-z_-]{35}')),
              ('Google opaque credential',re.compile(r'\bAQ\.[A-Za-z0-9_-]{25,}')),
              ('provider token',re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}')),
              ('private key',re.compile('-{5}BEGIN (?:RSA |EC )?PRIVATE KEY-{5}')),
              ('developer home path',re.compile(r'C:[/\\]Users[/\\](?!Public\b)[^/\\\s"\']+',re.I))]
    private_values=[]
    for name in ('firebase_key.json','jojo_owner_identity.json'):
        path=root/name
        if path.is_file():
            value=json.loads(path.read_text(encoding='utf-8'))
            private_values.extend(str(value[k]) for k in ('name','project_id','client_email','private_key_id') if value.get(k))
    for path in selected:
        relative=path.relative_to(root).as_posix()
        if path.is_symlink() or path.name in PRIVATE_NAMES or any(part in ('.git','__pycache__','voice_cache','hud_profile','build') for part in path.relative_to(root).parts):
            issues.append((relative,'private/generated path'));continue
        if path.suffix in ('.png','.glb'):continue
        text=path.read_text(encoding='utf-8-sig')
        for label,pattern in patterns:
            if pattern.search(text):issues.append((relative,label))
        if path.suffix=='.py' and not relative.startswith('tests/'):
            for node in ast.walk(ast.parse(text)):
                if not isinstance(node,ast.Assign):continue
                names=[target.id for target in node.targets if isinstance(target,ast.Name)]
                if not any(re.search(r'(?:API_KEYS?|SECRET|TOKEN|PASSWORD|GEMINI_KEYS)$',name,re.I) for name in names):continue
                try:value=ast.literal_eval(node.value)
                except (ValueError,TypeError):continue
                literals=value if isinstance(value,(tuple,list)) else [value]
                if any(isinstance(item,str) and len(item)>16 and not item.startswith(('your-','example-')) for item in literals):
                    issues.append((relative,'literal credential assignment'))
        public_credit_file=relative in ('README.md','LICENSE','JOJO_RELEASE_METADATA.json')
        if any(value and value.casefold() in text.casefold() and not (public_credit_file and value==public_developer) for value in private_values):issues.append((relative,'private owner/project identifier'))
    return issues

def export(selected,root=ROOT):
    issues=audit(selected,root)
    if issues:raise RuntimeError('Privacy scan failed: '+json.dumps(issues))
    target=root/'jojo_release_source.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        manifest={}
        for path in selected:
            name=path.relative_to(root).as_posix();data=path.read_bytes()
            archive.writestr('JoJo/'+name,data);manifest[name]=hashlib.sha256(data).hexdigest()
        archive.writestr('JoJo/JOJO_SOURCE_MANIFEST.json',json.dumps(manifest,indent=2))
    return target

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');parser.add_argument('--export',action='store_true')
    args=parser.parse_args();selected=files();issues=audit(selected)
    print(json.dumps({'source_files':len(selected),'issues':issues},indent=2))
    if issues:raise SystemExit(1)
    if args.export:print('Clean source snapshot:',export(selected))

if __name__=='__main__':main()
