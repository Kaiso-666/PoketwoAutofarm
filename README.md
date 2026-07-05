# 🤖 Pokétwo OCR Self-Bot Setup Guide
This guide will walk you through the installation and configuration of your streamlined Pokétwo OCR Self-Bot.
> **NOTE:** This Self-bot requires a helper bot (like Pokéname or P2 Assistant) to be present in the server to trigger the text/image cues.
> 
## 📋 Prerequisites
Before beginning, ensure you have:
 * **Python 3.10+:** Download from python.org.
   * *Windows Users:* **Crucial!** Check the box **"Add Python to PATH"** during installation.
 * **Write Permissions:** Ensure your user account has permission to create and modify files in your chosen directory.
## 🚀 Phase 1: Installation
Place requirements.txt, main.py, install.bat, and install.sh in the same folder.
### For Windows
 1. Double-click install.bat.
 2. The script will automatically install the lightweight dependencies: discord.py-self and aiohttp.
 3. A run.bat file will be created. Use this to start your bot in the future.
### For Linux, macOS, or Termux
 1. Open your terminal and navigate to the bot folder:
   ```bash
   cd /path/to/your/bot
   
   ```
 2. Make the script executable and run it:
   ```bash
   chmod +x install.sh
   ./install.sh
   
   ```
 3. Use the generated run.sh file to start the bot.
## ⚙️ Phase 2: API & Bot Configuration
Because image processing is handled externally via the API endpoint, you do **not** need to install Tesseract OCR or any graphics libraries on your local machine.
 1. Open main.py in a text editor.
 2. Locate the self.api_url line:
   ```python
   self.api_url = "https://pokeidentifierapi.onrender.com/predict"
   
   ```
   *Leave this as-is unless you are hosting a custom instance of the backend API.*
 3. Scroll to the very bottom of main.py and replace "hidden" with your actual Discord account token:
   ```python
   client.run("YOUR_DISCORD_TOKEN_HERE")
   
   ```
## ✅ Phase 3: Verification
Run your run.bat (Windows) or ./run.sh (Linux/Mac) and monitor the terminal.
**Success Look:**
```text
[*] Logged in as YourUsername#0000! Listening for messages... ☑

```
## 🛠️ Troubleshooting
| Error | Likely Cause | Solution |
|---|---|---|
| **ModuleNotFoundError** | A library failed to install correctly. | Run the install script again with Admin/Sudo privileges. |
| **Authentication Failed** | Your bot token in client.run(...) is invalid or expired. | Double-check that your token is correct and wrapped in quotes. |
| **API Image URL Error (Status 4xx/5xx)** | The remote image could not be reached or processed. | Ensure the bot has permission to view embed links in that channel. |
## 🛡️ Guild Exclusion
To disable the bot in specific servers, modify the self.excluded_guilds set in your main.py:
```python
# Add your server IDs here to ignore them
self.excluded_guilds = {123456789012345678, 987654321098765432}

```
> 💡 **Need more help?** Double-check your account token and ensure your network isn't blocking the API endpoint. Still stuck? Contact @kaiso5693 on Discord!