"""Deterministic companion action validation; model output cannot grant consent."""
import re
from jojo_policy import require_allowed, payment_surface, PAYMENT_HANDOFF

APP_CATALOG = {
    'com.amazon.mShop.android.shopping': 'Amazon',
    'com.flipkart.android': 'Flipkart',
    'com.whatsapp': 'WhatsApp',
    'org.telegram.messenger': 'Telegram',
    'com.instagram.android': 'Instagram',
    'com.google.android.youtube': 'YouTube',
    'com.google.android.apps.photos': 'Google Photos',
    'com.google.android.gm': 'Gmail',
    'com.google.android.apps.maps': 'Google Maps',
}
SYSTEM_APPS = {'contacts', 'dialer', 'messages', 'gallery', 'settings', 'wifi', 'bluetooth', 'display'}

def store_app_name(package):
    """Resolve a proposed package against Google's store, never an arbitrary host."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+', package):
        raise ValueError('Invalid app package')
    require_allowed(package)
    from urllib.request import urlopen, Request
    from urllib.parse import urlsplit
    from html.parser import HTMLParser
    class Metadata(HTMLParser):
        name = ''
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == 'meta' and values.get('property') == 'og:title':
                self.name = values.get('content', '')
    try:
        url = 'https://play.google.com/store/apps/details?id='+package+'&hl=en&gl=IN'
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=8) as response:
            if urlsplit(response.url).hostname != 'play.google.com':
                raise ValueError('Unexpected store destination')
            page = response.read(2_000_001)
            if len(page) > 2_000_000:
                raise ValueError('Store response too large')
        parser = Metadata(); parser.feed(page.decode('utf-8'))
        name = re.sub(r'\s*[-–] (Apps|Games) on Google Play$', '', parser.name).strip()
        if not name or len(name) > 120 or name.casefold() in {'google play', 'apps on google play'}:
            raise ValueError('Store app identity unavailable')
        require_allowed(name)
        return name
    except PermissionError:
        raise
    except Exception as exc:
        raise ValueError('Play Store par app verify nahi hua. Install nahi kiya; app ka exact naam batayein ya baad mein try karein.') from exc

def installed_packages(text):
    return {line.rsplit(' = ', 1)[1].strip() for line in text.splitlines() if ' = ' in line}

def affirmative(text):
    return re.sub(r'[.!?।,]+', '', text.casefold()).strip() in {
        'yes', 'yes install', 'install it', 'haan', 'ha', 'haa', 'haan kar do', 'haa kr de',
        'haan kr de', 'haan install kar do', 'kar do', 'kr de', 'हाँ', 'हां', 'हाँ कर दो',
        'हां कर दो', 'हाँ इंस्टॉल कर दो', 'हां इंस्टॉल कर दो', 'कर दो',
    }

def validate_action(action, apps, screen, install_grant=None):
    if not isinstance(action, dict):
        raise ValueError('Invalid action')
    kind = action.get('type')
    if kind not in {'click', 'type', 'scroll', 'open', 'open_system', 'back', 'finish', 'request_install', 'wait'}:
        raise ValueError('Unsupported mobile action')
    # Replies are not executable targets. A refusal can itself mention payments.
    if kind == 'finish':
        return dict(action)
    import json
    require_allowed(json.dumps({k: v for k, v in action.items() if k != 'reply'}, ensure_ascii=False))
    if kind == 'open_system' and action.get('app') not in SYSTEM_APPS:
        raise ValueError('Unknown system app')
    if kind in {'open', 'request_install'}:
        pkg = action.get('package', '')
        if pkg not in installed_packages(apps):
            return {'type': 'request_install', 'package': pkg, 'name': store_app_name(pkg)}
        return {'type': 'open', 'package': pkg}
    if kind in {'click', 'type', 'scroll'}:
        node = action.get('node')
        if type(node) is not int or node < 0:
            raise ValueError('An observed node is required')
        label = next((line for line in screen.splitlines() if line.startswith(str(node)+': ')), None)
        if label is None:
            raise ValueError('Node is not in the current observation')
        if payment_surface(label) or '[password field]' in label:
            raise PermissionError(PAYMENT_HANDOFF)
        if re.search(r'\binstall\b|इंस्टॉल|इंस्टाल', label, re.I) and not install_grant:
            raise PermissionError('App install karne se pehle owner ki haan chahiye.')
    # Model cannot provide native install grants or arbitrary intent URIs.
    return {k: v for k, v in action.items() if k in {'type', 'node', 'text', 'direction', 'app', 'package'}}
