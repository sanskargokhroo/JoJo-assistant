"""Shared restricted-app policy, independent of model prompts."""
import ctypes
import json
import os
import re
import unicodedata

BLOCKED = (
    'paytm', 'amazon pay', 'flipkart pay later', 'binance', 'बाइनेंस',
    'trustwallet', 'trust wallet', 'com.wallet.crypto.trustapp',
    'net.one97.paytm',
    'gpay', 'google pay', 'phonepe', 'bhim', 'cred', 'metamask',
    'com.google.android.apps.nbu.paisa.user', 'com.google.android.apps.walletnfcrel',
    'in.org.npci.upiapp', 'com.dreamplug.androidapp',
    'coinbase', 'bybit', 'bitget', 'kucoin', 'kraken', 'coindcx', 'wazirx',
    'coinswitch', 'zerodha', 'kite', 'groww', 'upstox', 'angel one',
    'robinhood', 'tradingview', 'netbanking', 'banking', 'yono',
    'payment app', 'trading app', 'crypto wallet', 'seed phrase',
    'private key', 'upi pin', 'cvv', 'otp', 'send money', 'transfer money',
)
REFUSAL = 'Paytm, payment, trading aur wallet apps JoJo ke liye restricted hain.'
PAYMENT_HANDOFF = 'Ab aap kijiye. Payment, PIN, OTP ya banking screen ko main access nahi kar sakta.'

def payment_surface(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    return bool(re.search(r'\b(checkout|check out|payment|pay|place order|buy now|upi|cvv|otp|card number|credit card|debit card|expiry date|billing details)\b|भुगतान|पेमेंट|खरीदें|ओटीपी', text))

def blocked_reason(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    compact = re.sub(r'[\s_.:/-]+', '', text)
    for word in BLOCKED:
        if len(word) <= 4:
            if re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text):
                return word
        elif re.sub(r'[\s_.:/-]+', '', word) in compact:
            return word
    return None

def require_allowed(value):
    if blocked_reason(value):
        raise PermissionError(REFUSAL)
    from jojo_security import inspect_link
    for url in re.findall(r'https?://[^\s<>"\']+', str(value), re.I):
        report = inspect_link(url.rstrip('.,)'))
        if report['risk'] == 'high':
            raise PermissionError('JoJo refused this URL: ' + '; '.join(f['message'] for f in report['findings']))

def foreground_title():
    if os.name != 'nt':
        return ''
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    title = ctypes.create_unicode_buffer(2048)
    user32.GetWindowTextW(user32.GetForegroundWindow(), title, len(title))
    return title.value

def guard_desktop(value=''):
    from jojo_capabilities import enabled
    if not enabled('desktop'):raise PermissionError('Desktop control is disabled in JoJo skills.')
    from jojo_runtime import target_platform
    target_platform('desktop')
    require_allowed(value)
    title = foreground_title()
    require_allowed(title)
    if payment_surface(title) or payment_surface(value):
        raise PermissionError(PAYMENT_HANDOFF)

def guard_tool(name, args):
    from jojo_capabilities import allowed_tool
    if not allowed_tool(name):raise PermissionError('This skill is disabled in the JoJo dashboard.')
    if name == 'inspect_link':
        # Passive string inspection is allowed even for a restricted destination.
        return
    require_allowed(json.dumps(args, ensure_ascii=False))
    from jojo_runtime import target_platform
    if target_platform() == 'mobile' and name in {
        'inspect_desktop_screen', 'click_ui_element', 'type_into_active_window',
        'press_keyboard_key', 'get_pc_system_diagnostics', 'read_local_file',
        'write_local_file', 'append_to_file', 'list_local_directory', 'search_local_files',
        'audit_device_security', 'inspect_app_file', 'deduplicate_and_organize_files','search_knowledge'}:
        raise PermissionError('This is a phone task; laptop tools are unavailable.')
    # Arbitrary code and self-installed code cannot enforce an app deny-list.
    if name in {'run_powershell', 'run_python_code', 'create_new_persistent_skill',
                'send_http_request', 'git_vcs_control', 'query_database_sqlite'}:
        raise PermissionError('Unrestricted code/network tools are disabled in restricted-app mode.')
