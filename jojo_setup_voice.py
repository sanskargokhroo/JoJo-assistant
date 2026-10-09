"""Install the local speaker-ID runtime and download its published ONNX model."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
MODEL_NAME = 'wespeaker_en_voxceleb_resnet34_LM.onnx'
URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/' + MODEL_NAME

def main():
    target = ROOT / '.jojo-deps/python'
    wheels = ROOT/'.jojo-deps/wheels'
    options = ['--no-index','--find-links',str(wheels)] if len(list(wheels.glob('*.whl'))) >= 2 else []
    subprocess.run([sys.executable, '-m', 'pip', 'install', *options,
                    '--target', str(target), 'sherpa-onnx==1.13.8'], check=True)
    model = ROOT / 'models' / MODEL_NAME
    model.parent.mkdir(exist_ok=True)
    if not model.exists():
        temporary = model.with_suffix('.download')
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open('wb') as out:
            while chunk := response.read(1024*1024):
                out.write(chunk)
        if temporary.stat().st_size != 26530550:
            raise RuntimeError('Unexpected model size; incomplete download was not activated.')
        temporary.replace(model)
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    if digest != 'e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012':
        raise RuntimeError('Model checksum does not match the verified release.')
    model.with_suffix('.json').write_text(json.dumps({'url': URL, 'sha256': digest,
        'license_reference': 'https://github.com/wenet-e2e/wespeaker',
        'runtime': 'sherpa-onnx 1.13.8'}, indent=2), encoding='utf-8')
    print('Local speaker model installed:', model.name, 'SHA256:', digest)

if __name__ == '__main__':
    main()
