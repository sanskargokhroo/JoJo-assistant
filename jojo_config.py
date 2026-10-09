"""Shared, local configuration. Environment variables override .env values."""
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines() if (ROOT / '.env').exists() else []:
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))

from jojo_user_config import private_dir, load as load_account
ACCOUNT = load_account()
PROVIDER = os.environ.get('JOJO_PROVIDER', ACCOUNT.get('provider','gemini')).lower()
DATA_DIR = private_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL = os.environ.get('JOJO_MODEL', ACCOUNT.get('model','gemini-3.5-flash-lite'))
API_TIMEOUT_MS = 30000
MAX_AGENT_STEPS = 24
MAX_TASK_SECONDS = 300

def api_keys():
    env_name={'gemini':'GEMINI_API_KEY','openai':'OPENAI_API_KEY','anthropic':'ANTHROPIC_API_KEY'}.get(PROVIDER)
    raw = (os.environ.get('GEMINI_API_KEYS') if PROVIDER=='gemini' else '') or os.environ.get(env_name or '', '') or ACCOUNT.get('api_key','')
    return [key.strip() for key in raw.split(',') if key.strip()]

def make_client(api_key=None):
    if PROVIDER!='gemini':
        from jojo_providers import ProviderClient
        keys=api_keys()
        if not api_key and not keys:raise RuntimeError('Run jojo_install.py to configure your own model key.')
        return ProviderClient(PROVIDER,api_key or keys[0])
    from google import genai
    from google.genai import types
    keys = api_keys()
    if not api_key and not keys:
        raise RuntimeError('Gemini API key missing. Set GEMINI_API_KEY in .env and restart JoJo.')
    return genai.Client(api_key=api_key or keys[0], http_options=types.HttpOptions(
        timeout=API_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))

def firebase_credential():
    if ACCOUNT:
        return ACCOUNT.get('firebase')
    path=Path(os.environ.get('JOJO_FIREBASE_CREDENTIALS',str(ROOT/'firebase_key.json')))
    return str(path) if path.is_file() else None

def read_preferences():
    try:
        values = json.loads((DATA_DIR / 'jojo_preferences.json').read_text(encoding='utf-8'))
        return values if isinstance(values, dict) else {}
    except (OSError, ValueError):
        return {}

_preferences_lock=threading.RLock()

def save_preferences(values):
    with _preferences_lock:
        previous = read_preferences()
        previous.update(values)
        path = DATA_DIR / 'jojo_preferences.json'
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(previous, indent=2), encoding='utf-8')
        temp.replace(path)
