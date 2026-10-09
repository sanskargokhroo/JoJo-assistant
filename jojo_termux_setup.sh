#!/data/data/com.termux/files/usr/bin/bash
# ==========================================
# 🚀 JoJo AGI - 1-Click Mobile Termux Installer
# Universal Mobile Control | Hands-Free Voice | Cloud Relay
# ==========================================

clear
echo "=========================================="
echo "🤖 JoJo AGI Universal Mobile Setup"
echo "=========================================="
echo "🚀 Connecting to JoJo Core..."

# Keep Termux running in background
echo "⚡ Acquiring background wake lock..."
termux-wake-lock 2>/dev/null || true

# Update packages and install prerequisites
echo "📦 Installing packages (curl, python, termux-api, pillow)..."
pkg update -y
pkg install -y python curl termux-api python-pillow

# Install requests and google-genai for reliable mobile vision & comms
pip install requests google-genai 2>/dev/null || true

# PC Core LAN URL
SERVER_URL="http://192.168.31.163:8000"

echo "📥 Downloading JoJo Mobile Companion & AI Vision Engine from $SERVER_URL..."
curl -sL "$SERVER_URL/jojo_mobile.py" -o "$HOME/jojo_mobile.py"
curl -sL "$SERVER_URL/jojo_mobile_vision.py" -o "$HOME/jojo_mobile_vision.py"
curl -sL "$SERVER_URL/jojo_config.py" -o "$HOME/jojo_config.py"
curl -sL "$SERVER_URL/jojo_policy.py" -o "$HOME/jojo_policy.py"

# Add aliases to bashrc
if ! grep -q "alias jojo=" "$HOME/.bashrc" 2>/dev/null; then
    echo "alias jojo=\"python \$HOME/jojo_mobile.py\"" >> "$HOME/.bashrc"
    echo "alias jojo-voice=\"python \$HOME/jojo_mobile.py --voice\"" >> "$HOME/.bashrc"
fi

echo "=========================================="
echo "✅ JoJo Mobile Setup Completed Successfully!"
echo "🛡️ Security Shield: GPay/PhonePe/Paytm/OTPs PERMANENTLY LOCKED"
echo "📱 Gmail, Chrome, Screen Lock/Unlock, Alarms, Settings, Torch, Calling & Notes READY!"
echo "👉 Normal Mode: type 'jojo'"
echo "👉 Hands-Free Voice Mode: type 'jojo-voice'"
echo "=========================================="

python "$HOME/jojo_mobile.py"
