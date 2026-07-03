#!/bin/bash

# Ensure we are in the script's directory
cd "$(dirname "$0")"

echo "[*] Checking for python3-venv..."
# Attempt to install venv if missing (Debian/Ubuntu/Termux)
if ! command -v python3 -m venv &> /dev/null; then
    echo "[!] venv module not found. Installing..."
    sudo apt update && sudo apt install python3-venv -y || pkg install python-venv -y
fi

echo "[*] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[*] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "[*] Creating launch script..."
    echo -e "#!/bin/bash\ncd \"\$(dirname \"\$0\")\"\nsource venv/bin/activate\npython3 autocatch.py" > run.sh
    chmod +x run.sh
    echo "[!] Setup complete! Run './run.sh' to start."
else
    echo "[!] Installation failed. Check your internet or package manager."
fi
