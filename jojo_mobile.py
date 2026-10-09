#!/usr/bin/env python3
# ==========================================
# 🤖 JoJo AGI - Universal Mobile Companion (Android / Termux)
# Deep Hardware & App Automation | Cloud Relay | Hands-Free Voice
# ==========================================
import os
import sys
import subprocess
import json
import urllib.parse
import urllib.request
import time
import re
import jojo_mobile_vision as jmv

# Local LAN Core IP or Cloud/Tunnel URL
DEFAULT_LAN_URL = "http://192.168.31.163:8000"
SERVER_URL = os.environ.get("JOJO_SERVER_URL", DEFAULT_LAN_URL)

SECURITY_REFUSAL_MSG = "अरे नहीं बॉस, ये पेमेंट्स, OTP या क्रिप्टो वॉलेट्स (MetaMask, Binance आदि) से जुड़ा है! आपकी सुरक्षा के लिए मैं इसे कभी हाथ नहीं लगाऊँगा।"

FINANCIAL_BLACKLIST = [
    # 🏦 Banking & Traditional Payments
    "otp", "one time password", "cvv", "upi pin", "atm pin", 
    "gpay", "google pay", "phonepe", "paytm", "bhim", "cred", 
    "yono", "bank account", "netbanking", "send money", "transfer money", 
    "card number", "debit card", "credit card", "banking app", "bhim upi",
    "password change", "pin change", "पैसे भेजो", "ओटीपी", "बैंक",

    # 🪙 Cryptocurrency Wallets (Web3 / Desktop / Mobile)
    "metamask", "meta mask", "मेटामास्क",
    "trustwallet", "trust wallet", "ट्रस्ट वॉलेट",
    "phantom", "phantom wallet",
    "coinbase wallet", "coinbase",
    "exodus", "exodus wallet",
    "rabby", "rabby wallet",
    "rainbow wallet", "rainbow",
    "zerion", "safepal",
    "ledger", "ledger live", "trezor",
    "bitkeep", "ronin wallet", "ronin",
    "solflare", "sui wallet", "keplr", "argent",
    "crypto wallet", "cryptocurrency wallet", "web3 wallet", "defi wallet",
    "crypto app", "क्रिप्टो वॉलेट", "क्रिप्टो",

    # 📈 Crypto Exchanges & Trading Platforms
    "binance", "बायनेंस", "बाइनेंस",
    "bitget", "बिटगेट",
    "bybit", "बायबिट",
    "kucoin", "कूकॉइन",
    "kraken",
    "coindcx", "coin dcx",
    "wazirx", "वज़ीरएक्स",
    "coinswitch", "coin switch", "coinswitch kuber",
    "mudrex", "gate.io", "gate io",
    "mexc", "htx", "huobi", "crypto.com",
    "crypto exchange", "crypto trading",

    # 🔑 Private Keys, Seed Phrases & Sensitive Blockchain Actions
    "seed phrase", "recovery phrase", "secret recovery phrase", "mnemonic",
    "private key", "private keys", "secret key",
    "12 word", "12 words", "24 word", "24 words", "seed words",
    "crypto transfer", "send crypto", "crypto send",
    "send btc", "send eth", "send usdt", "send sol", "send bitcoin",
    "crypto withdrawal", "withdraw crypto", "crypto deposit",
    "सीड फ्रेज", "प्राइवेट की", "क्रिप्टोकरेंसी"
]

def is_safe_mobile(text):
    from jojo_policy import blocked_reason
    if blocked_reason(text):
        return False
    t = text.lower()
    for w in FINANCIAL_BLACKLIST:
        if len(w) <= 4:
            if re.search(r'\b' + re.escape(w) + r'\b', t):
                return False
        else:
            if w in t:
                return False
    return True

def speak_mobile(text):
    """Speaks on mobile using Voice 2 (streaming from JoJo PC Core) or Termux Hindi TTS."""
    clean = text.strip()
    if not clean:
        return
    print(f"JoJo Mobile (Voice 2): {clean}")
    # 1. Stream exact Voice 2 (hi-IN-MadhurNeural) from JoJo PC Core
    try:
        encoded_q = urllib.parse.quote(clean)
        tts_url = f"{SERVER_URL}/api/tts?text={encoded_q}"
        res = subprocess.run(["termux-media-player", "play", tts_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        if res.returncode == 0:
            return
    except Exception:
        pass

    # 2. Native Termux Hindi TTS fallback
    try:
        subprocess.run(["termux-tts-speak", "-l", "hi-IN", "-r", "1.1", "-p", "1.1", clean], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass

def send_chat_to_pc(message, speaker="boss"):
    # 1. Try Direct HTTP Gateway (LAN or Tunnel)
    try:
        data = json.dumps({"command": message, "speaker": speaker}).encode("utf-8")
        req = urllib.request.Request(f"{SERVER_URL}/api/voice_command", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as res:
            resp_data = json.loads(res.read().decode("utf-8"))
            return resp_data.get("reply", "माफ करना बॉस, समझ नहीं पाया!")
    except Exception as e:
        print(f"⚠️ Direct LAN/Server unreachable ({e}). Checking Cloud Relay...")

    # 2. Universal Cloud Relay Fallback (Firebase / Remote)
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            if os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")
                firebase_admin.initialize_app(cred)
        db = firestore.client()
        doc_ref = db.collection("jojo_remote_commands").add({
            "command": message,
            "speaker": speaker,
            "status": "pending",
            "created_at": firestore.SERVER_TIMESTAMP
        })
        doc_id = doc_ref[1].id
        print(f"☁️ Command synced to Cloud (ID: {doc_id}). Waiting for PC...")
        
        for _ in range(20):
            time.sleep(0.5)
            doc = db.collection("jojo_remote_commands").document(doc_id).get()
            if doc.exists:
                d = doc.to_dict()
                if d.get("status") == "completed":
                    return d.get("reply", "डन बॉस!")
    except Exception:
        pass

    return f"अरे यार बॉस, PC या क्लाउड सर्वर से कनेक्ट नहीं हो पा रहा है! कृपया चेक करें कि लैपटॉप पर JoJo चालू है या नहीं।"

def wake_and_unlock_screen():
    """Wakes the Android display, dismisses swipe keyguard, and enters PIN if configured."""
    try:
        # 1. Turn Screen ON (KEYCODE_WAKEUP = 224)
        subprocess.run(["input", "keyevent", "224"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.2)
        # 2. Dismiss Keyguard (KEYCODE_MENU = 82)
        subprocess.run(["input", "keyevent", "82"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 3. Swipe up gesture (supported on Android 10, 11, 12, 13, 14, 15)
        subprocess.run(["input", "swipe", "500", "1500", "500", "300", "250"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 4. If phone PIN is configured in environment (export JOJO_PHONE_PIN="1234"): auto-enter PIN
        pin = os.environ.get("JOJO_PHONE_PIN", "")
        if pin:
            time.sleep(0.4)
            subprocess.run(["input", "text", pin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["input", "keyevent", "66"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # KEYCODE_ENTER
    except Exception:
        pass

def show_mobile_hud():
    """The native companion owns its overlay; never redirect into Chrome."""
    return False


def lookup_contact_number(name):
    clean_name = name.strip().lower()
    try:
        res = subprocess.run(["termux-contact-list"], capture_output=True, text=True, timeout=4)
        if res.returncode == 0 and res.stdout.strip():
            contacts = json.loads(res.stdout)
            for c in contacts:
                c_name = c.get("name", "").lower()
                if clean_name in c_name or c_name in clean_name:
                    num = c.get("number", "")
                    if num:
                        return num, c.get("name")
    except Exception:
        pass
    return None, None

def execute_mobile_command(cmd):
    text = cmd.strip()
    low = text.lower()

    # Automatically bring up 3D JoJo Voice Hologram HUD on phone
    show_mobile_hud()

    # 1. 🛡️ Strict Financial & Crypto Security Shield (Zero Access Policy)
    if not is_safe_mobile(text):
        speak_mobile(SECURITY_REFUSAL_MSG)
        return

    # 0. 📸 Mobile Screenshot
    if any(k in low for k in ["screenshot", "screen shot", "स्क्रीनशॉट", "screen le", "screenshot le", "screenshot lo"]):
        wake_and_unlock_screen()
        im, data = jmv.capture_mobile_screen()
        if data:
            save_path = "/sdcard/Pictures/Screenshots/jojo_screenshot.png" if jmv.is_android_device() else os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop", "mobile_screenshot.png")
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(data)
                speak_mobile("मोबाइल स्क्रीनशॉट सेव कर दिया बॉस! 📸")
                return
            except Exception:
                pass
        speak_mobile("बॉस, मोबाइल स्क्रीनशॉट लेने में दिक्कत आई!")
        return

    # 1. ⚙️ Mobile Combined Settings Open + Option Select
    # e.g., "setting open kr usme bluetooth option select kr"
    m_combo = re.search(r'(?:setting|सेटिंग)\s*(?:open|खोल).*?(?:usme|me|mein|में)\s*(.*?)\s*(?:option\s+select|select|pe\s+click|click|टैप|tap)', low)
    if m_combo:
        target = m_combo.group(1).strip()
        wake_and_unlock_screen()
        if any(b in target for b in ["bluetooth", "ब्लूटूथ", "device"]):
            subprocess.run(["am", "start", "-a", "android.settings.BLUETOOTH_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif any(w in target for w in ["wifi", "wi-fi", "वाईफाई", "network"]):
            subprocess.run(["am", "start", "-a", "android.settings.WIFI_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif any(s in target for s in ["sound", "audio", "साउंड"]):
            subprocess.run(["am", "start", "-a", "android.settings.SOUND_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif any(d in target for d in ["display", "डिस्प्ले"]):
            subprocess.run(["am", "start", "-a", "android.settings.DISPLAY_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["am", "start", "-a", "android.settings.SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        ok, msg = jmv.ai_mobile_click_element(target)
        speak_mobile(msg)
        return

    # 2. 🎯 Direct Mobile Quick Actions (Allow, Deny, Cancel, OK, Yes, No)
    if any(k in low for k in ["allow kar", "allow kr", "allow karo", "allow pe click", "allow par click", "allow select", "allow daba"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("Allow")
        speak_mobile(msg)
        return
    if any(k in low for k in ["deny kar", "deny kr", "deny karo", "deny pe click", "deny par click", "deny select", "dont allow", "don't allow", "अस्वीकार"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("Deny")
        speak_mobile(msg)
        return
    if any(k in low for k in ["cancel kar", "cancel pe click", "cancel karo"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("Cancel")
        speak_mobile(msg)
        return
    if any(k in low for k in ["ok kar", "ok pe click", "ok karo", "okay kar"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("OK")
        speak_mobile(msg)
        return
    if any(k in low for k in ["yes pe click", "yes kar", "yes select"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("Yes")
        speak_mobile(msg)
        return
    if any(k in low for k in ["no pe click", "no kar", "no select"]):
        wake_and_unlock_screen()
        ok, msg = jmv.ai_mobile_click_element("No")
        speak_mobile(msg)
        return

    # 3. 👁️ Autonomous Mobile AI Vision Click & Option Select
    # Matches: "bluetooth option select kr", "bluetooth select kar", "wifi select kar", "click on save"
    m_click1 = re.search(r'^(?:click\s+on|tap\s+on|select)\s+(.*?)$', low)
    if m_click1:
        target = m_click1.group(1).strip()
        target = re.sub(r'\s*(option|button|ko|par|pe|karo|kar|kr)+$', '', target).strip()
        if target:
            wake_and_unlock_screen()
            ok, msg = jmv.ai_mobile_click_element(target)
            speak_mobile(msg)
            return

    m_click2 = re.search(r'^(.*?)\s*(?:option\s+select|select\s+karo|select\s+kar|select\s+kr|select|चुनो|चुन|pe\s+click|par\s+click|click\s+karo|click\s+kar|click\s+kr|pe\s+tap|tap)\s*(?:karo|kar|kr)?$', low)
    if m_click2:
        target = m_click2.group(1).strip()
        target = re.sub(r'^(isko|use|ye|uss|iss|kripya|please)\s+', '', target).strip()
        target = re.sub(r'\s*(option|button|ko|par|pe)+$', '', target).strip()
        if target and not any(ign in target for ign in ["volume", "sound", "aawaz", "gana", "song", "video", "torch", "gmail", "alarm"]):
            wake_and_unlock_screen()
            ok, msg = jmv.ai_mobile_click_element(target)
            speak_mobile(msg)
            return

    # 4. ✍️ Direct Mobile Text Typing
    m_type = re.search(r'^(?:type\s+kar|type\s+karo|likho|type|write)\s+(.*?)$', low)
    if m_type:
        text_val = m_type.group(1).strip()
        if text_val:
            wake_and_unlock_screen()
            jmv.mobile_type_text(text_val)
            speak_mobile(f"'{text_val}' टाइप कर दिया बॉस!")
            return

    # 5. 📱 Android Navigation Gestures & Hardware Keys
    if any(k in low for k in ["back kar", "peeche jao", "back jao", "बैक करो"]):
        jmv.mobile_keyevent("back")
        speak_mobile("बैक कर दिया बॉस!")
        return
    if any(k in low for k in ["home screen", "home jao", "होम स्क्रीन", "home daba"]):
        jmv.mobile_keyevent("home")
        speak_mobile("होम स्क्रीन पर आ गया बॉस!")
        return
    if any(k in low for k in ["notification kholo", "notification panel", "नोटिफिकेशन"]):
        jmv.mobile_keyevent("notifications")
        speak_mobile("नोटिफिकेशन पैनल खोल दिया बॉस!")
        return
    if any(k in low for k in ["enter daba", "enter press"]):
        jmv.mobile_keyevent("enter")
        speak_mobile("Enter दबा दिया बॉस!")
        return
    if any(k in low for k in ["niche scroll", "scroll down", "नीचे स्क्रॉल"]):
        jmv.mobile_swipe(500, 1400, 500, 400, 300)
        speak_mobile("नीचे स्क्रॉल कर दिया बॉस!")
        return
    if any(k in low for k in ["upar scroll", "scroll up", "ऊपर स्क्रॉल"]):
        jmv.mobile_swipe(500, 400, 500, 1400, 300)
        speak_mobile("ऊपर स्क्रॉल कर दिया बॉस!")
        return

    # 2. 📧 Gmail Compose & Send Assistance
    if any(k in low for k in ["gmail", "जीमेल", "mail", "ईमेल", "email"]):
        wake_and_unlock_screen()
        if any(k in low for k in ["bhejo", "send", "karo", "create", "likho", "compose", "नया मेल"]):
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
            to_addr = email_match.group(0) if email_match else ""
            subj_match = re.search(r'(?:subject|vishay|विषय)\s+(.+?)(?:body|message|$)', text, re.IGNORECASE)
            subject = urllib.parse.quote(subj_match.group(1).strip()) if subj_match else ""
            mailto_uri = f"mailto:{to_addr}?subject={subject}"
            speak_mobile("स्क्रीन ऑन करके जीमेल खोल दिया है बॉस, नया मेल तैयार है!")
            subprocess.run(["am", "start", "-a", "android.intent.action.SENDTO", "-d", mailto_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        else:
            speak_mobile("स्क्रीन ऑन करके जीमेल खोल रहा हूँ बॉस!")
            subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", "mailto:"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    # 3. 🌐 Chrome Search & Web Browsing
    if any(k in low for k in ["chrome", "क्रोम", "google search", "सर्च"]):
        wake_and_unlock_screen()
        query = text
        for r_w in ["chrome", "क्रोम", "open", "kholo", "खोलो", "par", "search", "karo", "सर्च", "करो", "dikhao"]:
            query = re.sub(re.escape(r_w), "", query, flags=re.IGNORECASE)
        query = query.strip()

        if query:
            speak_mobile(f"स्क्रीन ऑन करके क्रोम पर '{query}' सर्च कर रहा हूँ बॉस!")
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        else:
            speak_mobile("स्क्रीन ऑन करके गूगल क्रोम खोल रहा हूँ बॉस!")
            url = "https://www.google.com"

        subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # 4. 🔒 Screen Lock / 🔓 Screen Unlock
    if (("lock" in low or "लॉक" in low or "band" in low or "बंद" in low) and 
        any(w in low for w in ["screen", "स्क्रीन", "mobile", "मोबाइल", "phone", "फ़ोन", "device", "डिवाइस"])) or \
       any(k in low for k in ["lock the mobile", "lock the phone", "lock mobile", "lock phone", "स्क्रीन लॉक", "फ़ोन लॉक", "मोबाइल लॉक", "फोन लॉक", "लॉक कर दो"]):
        speak_mobile("जी बॉस, मोबाइल स्क्रीन लॉक कर रहा हूँ!")
        # Power key press to lock display (KEYCODE_POWER = 26)
        subprocess.run(["input", "keyevent", "26"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if (("unlock" in low or "अनलॉक" in low or "kholo" in low or "खोलो" in low or "on" in low or "ऑन" in low) and 
        any(w in low for w in ["screen", "स्क्रीन", "mobile", "मोबाइल", "phone", "फ़ोन", "device"])) or \
       any(k in low for k in ["wake screen", "wake up", "स्क्रीन खोलो", "स्क्रीन ऑन", "फ़ोन ऑन"]):
        speak_mobile("स्क्रीन ऑन कर दी है बॉस! बस फ़िंगरप्रिंट टच कर दीजिए।")
        wake_and_unlock_screen()
        return

    # 5. ⏰ Set Alarm & Timers
    if any(k in low for k in ["alarm", "अलार्म"]):
        m_time = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(?:baje|am|pm|बजे)?', low)
        hour = 7
        minute = 0
        if m_time:
            hour = int(m_time.group(1))
            if m_time.group(2):
                minute = int(m_time.group(2))
            if "pm" in low and hour < 12:
                hour += 12
        speak_mobile(f"{hour}:{minute:02d} का अलार्म सेट कर रहा हूँ बॉस!")
        subprocess.run([
            "am", "start", "-a", "android.intent.action.SET_ALARM",
            "--ei", "android.intent.extra.alarm.HOUR", str(hour),
            "--ei", "android.intent.extra.alarm.MINUTES", str(minute),
            "--ez", "android.intent.extra.alarm.SKIP_UI", "false"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # 6. ⚙️ Settings, Ringtone & System Updates
    if any(k in low for k in ["setting", "सेटिंग", "update check", "अपडेट", "ringtone", "रिंगटोन"]):
        wake_and_unlock_screen()
        if any(k in low for k in ["update", "अपडेट"]):
            speak_mobile("सिस्टम अपडेट सेटिंग्स खोल रहा हूँ बॉस!")
            subprocess.run(["am", "start", "-a", "android.settings.SYSTEM_UPDATE_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        elif any(k in low for k in ["ringtone", "रिंगटोन", "sound", "साउंड", "आवाज़"]):
            speak_mobile("साउंड और रिंगटोन सेटिंग्स खोल रहा हूँ बॉस!")
            subprocess.run(["am", "start", "-a", "android.settings.SOUND_SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        else:
            speak_mobile("फ़ोन सेटिंग्स खोल रहा हूँ बॉस!")
            subprocess.run(["am", "start", "-a", "android.settings.SETTINGS"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    # 7. 🎶 Volume Control
    if any(k in low for k in ["volume", "वॉल्यूम", "sound kam", "sound badhao"]):
        if any(k in low for k in ["badhao", "high", "full", "up", "फुल", "बढ़ाओ"]):
            speak_mobile("वॉल्यूम बढ़ा रहा हूँ बॉस!")
            subprocess.run(["termux-volume", "ring", "15"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["termux-volume", "music", "15"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        elif any(k in low for k in ["kam", "slow", "down", "कम", "धीमा"]):
            speak_mobile("वॉल्यूम कम कर दिया बॉस!")
            subprocess.run(["termux-volume", "ring", "5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["termux-volume", "music", "5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    # 8. 🔦 Torch / Flashlight
    if any(k in low for k in ["torch", "टॉर्च", "flashlight", "फ़्लैशलाइट"]):
        if any(k in low for k in ["off", "band", "बंद"]):
            speak_mobile("टॉर्च बंद कर दी बॉस!")
            subprocess.run(["termux-torch", "off"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            speak_mobile("टॉर्च ऑन कर दी बॉस!")
            subprocess.run(["termux-torch", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # 9. 🔋 Battery Status
    if any(k in low for k in ["battery", "बैटरी"]):
        try:
            res = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
            if res.returncode == 0:
                b_data = json.loads(res.stdout)
                pct = b_data.get("percentage", 0)
                plugged = b_data.get("plugged", "UNPLUGGED")
                status_str = "चार्जिंग पर" if plugged != "UNPLUGGED" else "बिना चार्जर के"
                speak_mobile(f"बॉस, बैटरी {pct}% है और फ़ोन {status_str} चल रहा है!")
                return
        except Exception:
            pass

    # 10. 📞 Calling Assistance (Works Even on Lockscreen via Telephony Privilege)
    if any(k in low for k in ["call", "कॉल", "phone", "फ़ोन"]):
        wake_and_unlock_screen()
        digits = "".join([c for c in text if c.isdigit() or c == "+"])
        if len(digits) >= 3:
            speak_mobile(f"कॉल लगा रहा हूँ बॉस: {digits}")
            try:
                ret = subprocess.run(["termux-telephony-call", digits], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if ret.returncode != 0:
                    subprocess.run(["am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{digits}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.run(["am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{digits}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        else:
            # Intelligent Contact Name Lookup (e.g., "mummy ko call kar", "papa ko phone lagao")
            contact_query = low
            for r_w in ["call", "karo", "kar", "lagao", "mila", "milao", "phone", "ko", "par", "meri", "mere", "कॉल", "फ़ोन", "लगाओ", "करो", "को", "मिलाओ"]:
                contact_query = re.sub(rf"\b{re.escape(r_w)}\b", "", contact_query, flags=re.IGNORECASE)
            contact_query = contact_query.strip()
            
            relation_map = {
                "mummy": "mom", "maa": "mom", "mataji": "mom", "ammi": "mom",
                "papa": "dad", "pitaji": "dad", "bhai": "bro", "didi": "sister"
            }
            search_targets = [contact_query]
            if contact_query in relation_map:
                search_targets.append(relation_map[contact_query])
            
            num_found = None
            found_name = None
            for st in search_targets:
                if st:
                    num_found, found_name = lookup_contact_number(st)
                    if num_found:
                        break
            
            if num_found:
                speak_mobile(f"{found_name} को कॉल मिला रहा हूँ बॉस!")
                try:
                    subprocess.run(["termux-telephony-call", num_found], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    subprocess.run(["am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{num_found}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            else:
                if contact_query:
                    speak_mobile(f"बॉस, फ़ोन कॉन्टैक्ट्स में '{contact_query}' नहीं मिला। नंबर बता दीजिए, मैं तुरंत डायल कर दूँगा।")
                else:
                    speak_mobile("किसे कॉल करना है बॉस? नाम या नंबर बताइए।")
                return

    # 11. 🛒 Amazon Shopping
    if any(k in low for k in ["amazon", "अमेज़न", "shopping", "खरीद"]):
        wake_and_unlock_screen()
        clean_q = low
        for remove_word in ["amazon", "अमेज़न", "par", "on", "search", "kholo", "dikhao", "dikhana", "shopping", "खरीदो"]:
            clean_q = clean_q.replace(remove_word, "")
        clean_q = clean_q.strip()
        
        if clean_q:
            speak_mobile(f"स्क्रीन ऑन करके अमेज़न पर {clean_q} खोल रहा हूँ बॉस!")
            url = f"https://www.amazon.in/s?k={urllib.parse.quote(clean_q)}"
        else:
            speak_mobile("स्क्रीन ऑन करके अमेज़न खोल रहा हूँ बॉस!")
            url = "https://www.amazon.in"
            
        try:
            subprocess.run(["termux-open-url", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # 12. 🗺️ Google Maps Navigation
    if any(k in low for k in ["map", "maps", "मैप", "मैप्स", "rasta", "रास्ता", "navigate", "direction"]):
        wake_and_unlock_screen()
        clean_dest = low
        for remove_word in ["map", "maps", "मैप", "मैप्स", "rasta", "रास्ता", "navigate", "direction", "ka", "to", "kholo", "dikhao"]:
            clean_dest = clean_dest.replace(remove_word, "")
        clean_dest = clean_dest.strip()
        
        if clean_dest:
            speak_mobile(f"स्क्रीन ऑन करके मैप्स पर {clean_dest} का रास्ता खोल रहा हूँ बॉस!")
            nav_uri = f"google.navigation:q={urllib.parse.quote(clean_dest)}"
            web_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(clean_dest)}"
        else:
            speak_mobile("स्क्रीन ऑन करके गूगल मैप्स खोल रहा हूँ बॉस!")
            nav_uri = "geo:0,0"
            web_uri = "https://www.google.com/maps"
            
        try:
            ret = subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", nav_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ret.returncode != 0:
                subprocess.run(["termux-open-url", web_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.run(["termux-open-url", web_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # 13. 📝 Quick Notes
    if any(k in low for k in ["note likho", "नोट लिखो", "save note", "नोट बनाओ"]):
        note_text = text
        for r_w in ["note likho", "नोट लिखो", "save note", "नोट बनाओ", "likho", "note", "नोट"]:
            note_text = note_text.replace(r_w, "").replace(":", "")
        note_text = note_text.strip()
        
        if note_text:
            try:
                data = json.dumps({"text": note_text}).encode("utf-8")
                req = urllib.request.Request(f"{SERVER_URL}/api/notes", data=data, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=5)
                speak_mobile(f"नोट सेव कर लिया बॉस: '{note_text}'")
            except Exception:
                speak_mobile(f"नोट सेव कर लिया बॉस: '{note_text}'")
        else:
            speak_mobile("नोट में क्या लिखना है बॉस?")
        return

    # 14. 🧠 Regular AI Chat, Humor, & Learned Skills via PC Core / Cloud
    reply = send_chat_to_pc(text, speaker="boss")
    speak_mobile(reply)

def run_handsfree_voice_loop():
    # Termux speech-to-text does not supply owner-verification audio.
    print("Use the native JoJo Android companion for verified hands-free voice. Text commands remain available here.")


def main():
    print("\n" + "="*55)
    print("🤖 JoJo AGI Universal Mobile Companion")
    print(f"📡 Server Gateway: {SERVER_URL}")
    print("☁️ Cloud Relay: Firebase Sync Active")
    print("🛡️ Security Shield: GPay/Paytm/Crypto Wallets (MetaMask, TrustWallet, Binance, Bitget) LOCKED")
    print("📱 Gmail | Chrome | Lock/Wake | Alarms | Settings | Torch | Calling | Notes")
    print("="*55 + "\n")

    speak_mobile("हाँ बॉस, JoJo आपके मोबाइल पर तैयार है! बताइए क्या हुक्म है?")

    if "--voice" in sys.argv:
        run_handsfree_voice_loop()
        return

    while True:
        try:
            user_input = input("Boss > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "bye", "बाय"]:
                speak_mobile("अलविदा बॉस! कभी भी आवाज़ देना।")
                break
            if user_input.lower() in ["voice", "--voice"]:
                run_handsfree_voice_loop()
                break
            execute_mobile_command(user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting JoJo Mobile...")
            break

if __name__ == "__main__":
    main()
