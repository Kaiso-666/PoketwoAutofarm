import discord
import re
import aiohttp
import asyncio

# --- ANSI Terminal Colors Configuration ---
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
        
        # Track if the bot just sent a catch command
        self.sent_catch_attempt = False
        
        # Target user IDs (supporter bots Pokéname & some other)
        self.target_user_1 = 874910942490677270
        self.target_user_2 = 854233015475109888
        self.poketwo_id = 716390085896962058
        
        # Guild ID exclusion list
        self.excluded_guilds = {1520755884693913703, 676767676767676767}
        
        # Pattern to extract Level, Name, Gender, and IVs from the success string
        self.success_pattern = re.compile(r"You caught a Level (\d+) (.+?)(<:female:\d+>|<:male:\d+>|<:unknown:\d+>)? \(([\d.]+)%\)!")
        
        # Base API Configuration (Update this URL if hosting on Render/VPS)
        self.api_url = "https://pokeidentifierapi.onrender.com/predict"

    async def on_ready(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        print(f'{Colors.GREEN}[*]{Colors.RESET} Logged in as {Colors.BOLD}{Colors.CYAN}{self.user}{Colors.RESET}! Listening for messages... ☑')

    async def on_message(self, message):
        if message.guild and message.guild.id in self.excluded_guilds:
            return
            
        content = message.content.strip() if message.content else ""
        
        # --- Pokétwo Success / Fail / Captcha Tracker ---
        if message.author.id == self.poketwo_id:
            if f"Whoa there. Please tell us you're human! https://verify.poketwo.net/captcha/{self.user.id}" in content:
                link = f"https://verify.poketwo.net/captcha/{self.user.id}"
                blue_link = f"\033[34m\033]8;;{link}\033\\{link}\033]8;;\033\\{Colors.YELLOW}"
                
                print(f"\n{Colors.YELLOW}⚠ Pokétwo is requesting human verification, visit {blue_link} to verify your account then restart this bot. {Colors.RESET}")
                print(f"{Colors.RED}{Colors.BOLD}[-] Shutting down bot processes... 𐄂{Colors.RESET}")
                
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
                            if ":female:" in gender_raw:
                                gender = f"{Colors.MAGENTA}♀{Colors.RESET}"
                            elif ":male:" in gender_raw:
                                gender = f"{Colors.BLUE}♂{Colors.RESET}"
                            elif ":unknown:" in gender_raw:
                                gender = f"{Colors.WHITE}?{Colors.RESET}"
                                                        
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] Caught a [{lvl}] {name} ({iv}% IV) {gender}! ☑{Colors.RESET}")
                    else:
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] SUCCESS: {content} ☑{Colors.RESET}")
                self.sent_catch_attempt = False 
            return
            
        # --- Target User Verification ---
        if message.author.id not in (self.target_user_1, self.target_user_2):
            return
            
        if message.guild:
            bot_permissions = message.channel.permissions_for(message.guild.me)
            if not bot_permissions.send_messages:
                return

        server_name = message.guild.name if message.guild else "DMs"
        channel_name = message.channel.name if getattr(message.channel, "name", None) else "Unknown"

        # --- 1. Text Match Logic Pipeline (First Priority) ---
        if content:
            best_match = None
            try:
                # Pass the text to the API and let it handle validation rules
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
                    return # Match found! Exit early and bypass image/OCR fallback

        # --- 2. Fallback / OCR Logic Execution Pipeline ---
        # Fires if message had no text, or text failed your API's backend validation rules
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

        # Send the raw URL link straight to the API instead of downloading it locally first
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

client = OcrSelfBot()
client.run("YourTokenHere")