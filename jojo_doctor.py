"""Local diagnostics; network/model checks only when explicitly requested."""
import argparse
import importlib.util
import json
import sys
from jojo_config import MODEL, api_keys, make_client

def multiply(a: int, b: int) -> int:
    """Multiply two integers and return the calculated result."""
    return a * b

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', action='store_true', help='Check configured Gemini model availability')
    parser.add_argument('--smoke-agent', action='store_true', help='Live tool-loop check using arithmetic only')
    parser.add_argument('--smoke-files', action='store_true', help='Live write/read verification in a temporary directory')
    parser.add_argument('--audio', action='store_true', help='List audio devices without recording')
    parser.add_argument('--model-name', help='Test an alternative model without changing saved settings')
    parser.add_argument('--list-models', action='store_true', help='List available generation model names')
    args = parser.parse_args()
    global MODEL
    if args.model_name:
        import jojo_config
        jojo_config.MODEL = MODEL = args.model_name
    modules = ['tkinter', 'google.genai', 'speech_recognition', 'firebase_admin', 'fastapi', 'uvicorn',
        'pyautogui', 'numpy', 'sounddevice', 'soundfile', 'scipy', 'PIL', 'bs4', 'edge_tts', 'pyttsx3']
    missing = []
    for name in modules:
        try:
            if not importlib.util.find_spec(name):
                missing.append(name)
        except ImportError:
            missing.append(name)
    report = {'python': sys.version.split()[0], 'missing_modules': missing,
        'api_configured': bool(api_keys()), 'configured_model': MODEL}
    print(json.dumps(report, indent=2))
    if missing:
        return 1
    if args.audio:
        import sounddevice as sd
        try:
            print(sd.query_devices())
        except Exception as exc:
            print('Audio device query failed:', type(exc).__name__)
            return 1
    if args.model or args.smoke_agent or args.list_models or args.smoke_files:
        try:
            with make_client() as client:
                if args.list_models:
                    for model in client.models.list():
                        if 'generateContent' in (model.supported_actions or []):
                            print(model.name)
                if args.model:
                    model = client.models.get(model=MODEL)
                    print('Model available:', model.name)
                if args.smoke_agent:
                    from jojo_agent_loop import run_tool_loop
                    result = run_tool_loop(client,
                        'Use multiply to calculate 6 times 7, then call finish_task with the result and evidence step.',
                        'You are testing a function calling integration. Use only the provided arithmetic tool.',
                        [multiply], max_steps=6, time_limit=90)
                    print('Agent status:', result.status)
                    print('Agent reply:', result.reply)
                    print('Executed tools:', [step['tool'] for step in result.steps])
                    if result.status != 'completed' or not any(step['result'] == '42' and step['ok'] for step in result.steps):
                        return 1
                if args.smoke_files:
                    import tempfile
                    from pathlib import Path
                    from jojo_agent_loop import run_tool_loop
                    with tempfile.TemporaryDirectory(prefix='jojo-smoke-') as directory:
                        target = Path(directory) / 'check.txt'
                        def save_test_note(content: str) -> str:
                            """Write the test note in the isolated temporary test directory."""
                            target.write_text(content, encoding='utf-8')
                            return 'Test note written. Read it back to verify.'
                        def read_test_note() -> str:
                            """Read back the isolated test note to verify its content."""
                            return target.read_text(encoding='utf-8')
                        result = run_tool_loop(client,
                            'Write exactly JOJO_NATIVE_OK to the test note, read it back, then finish with evidence from the read step.',
                            'Use only the provided test-note tools. Verify every requested part.',
                            [save_test_note, read_test_note], max_steps=8, time_limit=90)
                        names = [step['tool'] for step in result.steps]
                        print('File task:', result.status, names)
                        print('File reply:', result.reply)
                        if (result.status != 'completed' or names != ['save_test_note', 'read_test_note']
                                or target.read_text(encoding='utf-8') != 'JOJO_NATIVE_OK'):
                            return 1
        except Exception as exc:
            print('Model check failed:', type(exc).__name__, 'code:', getattr(exc, 'code', 'unavailable'))
            return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
