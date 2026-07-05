#!/bin/bash
set -e

echo "====================================================="
echo "   Discord Self-Bot Installer (Auto-Start Enabled)   "
echo "====================================================="

# 1. Gather Filename
read -p "[?] Enter the desired filename: " RAW_FILENAME
FILENAME="${RAW_FILENAME%.py}.py"
CURRENT_DIR=$(realpath ".")

# 2. Interactive Token Validation Loop
while true; do
    read -p "[?] Enter your Discord Token: " USER_TOKEN
    echo "[*] Verifying token with Discord API..."
    
    # Perform a live verification ping against Discord's endpoint
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: $USER_TOKEN" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" https://discord.com/api/v9/users/@me)
    
    if [ "$STATUS" -eq 200 ]; then
        echo -e "\033[32m[+] Token verified successfully!\033[0m"
        echo "$USER_TOKEN" > "$CURRENT_DIR/.token"
        rm -f "$CURRENT_DIR/.token_invalid"
        break
    else
        echo -e "\033[31m[-] Invalid Token (API Status: $STATUS). Please try again.\033[0m"
    fi
done

# 3. Smart Environment Provisioning (Termux vs Linux)
echo -e "\n[*] Installing environment dependencies..."

if [ -n "$TERMUX_VERSION" ] || echo "$PREFIX" | grep -q "com.termux"; then
    echo "[!] Termux environment detected. Installing without sudo..."
    pkg update -y
    pkg install -y python curl
else
    echo "[!] Standard Linux detected. Installing with sudo apt..."
    sudo apt update
    sudo apt install -y python3 python3-pip curl
fi

echo -e "\n[*] Installing required Python packages..."
pip3 install aiohttp discord.py-self --break-system-packages || pip3 install aiohttp discord.py --break-system-packages || true

# 4. Write Self-Bot Script 
echo -e "\n[*] Creating automation file: $FILENAME"
cat << 'EOF' > "$FILENAME"
import discord
import re
import aiohttp
import asyncio
import os
import sys

# --- Token and State Management ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, ".token")
INVALID_FLAG = os.path.join(SCRIPT_DIR, ".token_invalid")

def get_secure_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return ""

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

class OcrSelfBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None
        self.sent_catch_attempt = False
        self.target_user_1 = 874910942490677270
        self.target_user_2 = 854233015475109888
        self.poketwo_id = 716390085896962058
        self.excluded_guilds = {1520755884693913703, 676767676767676767}
        self.success_pattern = re.compile(r"You caught a Level (\d+) (.+?)(<:female:\d+>|<:male:\d+>|<:unknown:\d+>)? \(([\d.]+)%\)!")
        self.api_url = "https://pokeidentifierapi.onrender.com/predict"

    async def on_ready(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        print(f'{Colors.GREEN}[*]{Colors.RESET} Logged in as {Colors.BOLD}{Colors.CYAN}{self.user}{Colors.RESET}! Listening for messages... ☑')

    async def on_message(self, message):
        if message.guild and message.guild.id in self.excluded_guilds:
            return
        content = message.content.strip() if message.content else ""
        
        if message.author.id == self.poketwo_id:
            if f"Whoa there. Please tell us you're human! https://verify.poketwo.net/captcha/{self.user.id}" in content:
                link = f"https://verify.poketwo.net/captcha/{self.user.id}"
                blue_link = f"\033[34m\033]8;;{link}\033\\{link}\033]8;;\033\\{Colors.YELLOW}"
                print(f"\n{Colors.YELLOW}⚠ Pokétwo is requesting human verification, visit {blue_link} to verify your account then restart this bot. {Colors.RESET}")
                if self.session and not self.session.closed:
                    await self.session.close()
                await self.close()
                return
            elif "That is the wrong pokémon!" in content:
                if self.sent_catch_attempt:
                    print(f"{Colors.RED}[-] Catch Failed: Incorrect Pokémon name guessed.{Colors.RESET}")
                self.sent_catch_attempt = False 
            elif "Congratulations" in content:
                if f"Congratulations <@{self.user.id}>!" in content:
                    match = self.success_pattern.search(content)
                    if match:
                        lvl = match.group(1)
                        name = match.group(2).strip()
                        gender_raw = match.group(3)
                        iv = match.group(4)
                        gender = ""
                        if gender_raw:
                            if ":female:" in gender_raw: gender = f"{Colors.MAGENTA}♀{Colors.RESET}"
                            elif ":male:" in gender_raw: gender = f"{Colors.BLUE}♂{Colors.RESET}"
                            elif ":unknown:" in gender_raw: gender = f"{Colors.WHITE}?{Colors.RESET}"
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] Caught a [{lvl}] {name} ({iv}% IV) {gender}! ☑{Colors.RESET}")
                    else:
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] SUCCESS: {content} ☑{Colors.RESET}")
                self.sent_catch_attempt = False 
            return
            
        if message.author.id not in (self.target_user_1, self.target_user_2):
            return
        if message.guild:
            bot_permissions = message.channel.permissions_for(message.guild.me)
            if not bot_permissions.send_messages: return

        server_name = message.guild.name if message.guild else "DMs"
        channel_name = message.channel.name if getattr(message.channel, "name", None) else "Unknown"

        if content:
            best_match = None
            try:
                async with self.session.post(self.api_url, data={"text": content}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        best_match = data.get("pokemon")
            except Exception as e:
                print(f"{Colors.RED}[!] API Text Endpoint Error: {e}{Colors.RESET}")

            if best_match:
                async with message.channel.typing():
                    response_msg = f"<@716390085896962058> c {best_match}"
                    await asyncio.sleep(0.2)
                    await message.channel.send(response_msg)
                    log_format = f"@Pokétwo c {best_match} [{server_name}>{channel_name}]"
                    print(f"{Colors.CYAN}[+] Sent (API Text Match): {Colors.RESET}{Colors.BOLD}{log_format}{Colors.RESET}")
                    self.sent_catch_attempt = True 
                    return 

        await asyncio.sleep(1.0)
        image_url = None
        if message.author.id == self.target_user_1:
            if message.attachments and getattr(message.attachments[0], 'content_type', None) and message.attachments[0].content_type.startswith('image/'):
                image_url = message.attachments[0].url
            elif message.embeds:
                for embed in message.embeds:
                    if embed.image and embed.image.url:
                        image_url = embed.image.url
                        break
                    elif embed.thumbnail and embed.thumbnail.url:
                        image_url = embed.thumbnail.url
                        break

        if image_url:
            try:
                async with message.channel.typing():
                    async with self.session.post(self.api_url, data={"image_url": image_url}) as api_resp:
                        if api_resp.status == 200:
                            result = await api_resp.json()
                            best_match = result.get("pokemon")
                            if best_match:
                                response_msg = f"<@716390085896962058> c {best_match}"
                                await message.channel.send(response_msg)
                                log_format = f"@Pokétwo c {best_match} [{server_name}>{channel_name}]"
                                print(f"{Colors.CYAN}[+] Sent (API OCR Match): {Colors.RESET}{Colors.BOLD}{log_format}{Colors.RESET}")
                                self.sent_catch_attempt = True
                        else:
                            print(f"{Colors.YELLOW}[-] API Image URL Error: Status Code {api_resp.status}{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}[!] Error passing image URL to API: {e}{Colors.RESET}")

# Execution wrapping with dynamic failure catching
client = OcrSelfBot()
TOKEN = get_secure_token()

try:
    if not TOKEN:
        raise discord.LoginFailure("Token payload found empty.")
    client.run(TOKEN)
except Exception as e:
    if "LoginFailure" in type(e).__name__ or "Improper token" in str(e):
        with open(INVALID_FLAG, "w") as flag_file:
            flag_file.write("invalid")
        print(f"\033[31m[!] Authentication Failed: Token has expired or is invalid. Recovery flag raised.\033[0m")
    else:
        print(f"\033[31m[!] Unhandled Runtime Interruption: {e}\033[0m")
    sys.exit(1)
EOF

# 5. Injecting Interactive Recovery Engine into Bash Startup Profile
echo -e "\n[*] Structuring persistent background runner inside ~/.bashrc..."

cat << EOF >> ~/.bashrc

# --- Discord Bot Auto-Start & Token Recovery System ---
if [ -f "$CURRENT_DIR/.token_invalid" ] || [ ! -f "$CURRENT_DIR/.token" ] || [ ! -s "$CURRENT_DIR/.token" ]; then
    echo -e "\n\033[33m[!] [Discord Bot Alert]: Token is expired or missing. Repair required!\033[0m"
    while true; do
        read -p "[?] Enter a valid replacement Discord Token: " NEW_TOKEN
        STATUS=\$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: \$NEW_TOKEN" -H "User-Agent: Mozilla/5.0" https://discord.com/api/v9/users/@me)
        if [ "\$STATUS" -eq 200 ]; then
            echo "\$NEW_TOKEN" > "$CURRENT_DIR/.token"
            rm -f "$CURRENT_DIR/.token_invalid"
            echo -e "\033[32m[+] Token successfully updated and validated!\033[0m"
            break
        else
            echo -e "\033[31m[-] Token rejection from Discord (HTTP \$STATUS). Try again.\033[0m"
        fi
    done
fi

# Confirm background instance initialization
if ! pgrep -f "python3 $CURRENT_DIR/$FILENAME" > /dev/null; then
    python3 "$CURRENT_DIR/$FILENAME" > /dev/null 2>&1 &
fi
# ------------------------------------------------------
EOF

# 6. Immediate Execution Trigger
echo -e "\n[*] Spinning up the bot instance immediately..."
if ! pgrep -f "python3 $CURRENT_DIR/$FILENAME" > /dev/null; then
    python3 "$CURRENT_DIR/$FILENAME" > /dev/null 2>&1 &
    echo -e "\033[32m[+] Bot successfully initialized and active in the background! ☑\033[0m"
else
    echo -e "\033[33m[!] Bot instance is already running.\033[0m"
fi

echo -e "\n\033[32m[✔] Provisioning Pipeline Complete!\033[0m"
echo "[*] Application Script: $CURRENT_DIR/$FILENAME"
echo "[*] Token File Location: $CURRENT_DIR/.token"
