import discord
import re
import io
import aiohttp
import pytesseract
import asyncio
import difflib
from PIL import Image, ImageEnhance, ImageDraw

# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# using tesseract is a pain in the ahh

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
        self.pokemon_dict = {}             
        self.pokemon_normalized_names = [] 
        
        # Track if the bot just sent a catch command
        self.sent_catch_attempt = False
        
        # Target user IDs (supporter bots Pokéname & some other)
        self.target_user_1 = 874910942490677270
        self.target_user_2 = 854233015475109888
        self.poketwo_id = 716390085896962058
        
        # Guild ID exclusion list
        self.excluded_guilds = {1520755884693913703, 676767676767676767} # guilds/servers where u wanna don't grind
        
        # Pre-compile regex patterns
        self.alnum_regex = re.compile(r"[^a-zA-Z0-9\-\']")
        self.normalization_regex = re.compile(r"[^a-z0-9]")
        self.new_user_pattern = re.compile(r"^([^:]+):\s*\d+%\s*$")
        
        # Pattern to extract Level, Name, Gender, and IVs from the success string
        self.success_pattern = re.compile(r"You caught a Level (\d+) (.+?)(<:female:\d+>|<:male:\d+>)? \(([\d.]+)%\)!")
        
        self.load_pokemon_database()

    def normalize_name(self, text):
        return self.normalization_regex.sub("", text.lower())

    def load_pokemon_database(self):
        try:
            with open("pokenames.txt", "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if name:
                        normalized = self.normalize_name(name)
                        self.pokemon_dict[normalized] = name
            
            self.pokemon_normalized_names = list(self.pokemon_dict.keys())
            print(f"{Colors.MAGENTA}[*]{Colors.RESET} Loaded {Colors.BOLD}{len(self.pokemon_dict)}{Colors.RESET} Pokémon names into memory.")
        except FileNotFoundError:
            print(f"{Colors.RED}{Colors.BOLD}[!] Warning: pokenames.txt not found. Matching will not work.{Colors.RESET}")

    def get_best_match(self, extracted_text):
        if not extracted_text or not self.pokemon_dict:
            return None
            
        entire_block_norm = self.normalize_name(extracted_text)
        if entire_block_norm in self.pokemon_dict:
            return self.pokemon_dict[entire_block_norm]
            
        words = extracted_text.split()
        for word in words:
            word_norm = self.normalize_name(word)
            if word_norm in self.pokemon_dict:
                return self.pokemon_dict[word_norm]
                
        matches = difflib.get_close_matches(entire_block_norm, self.pokemon_normalized_names, n=1, cutoff=0.75)
        if matches:
            return self.pokemon_dict[matches[0]]
            
        return None

    def process_image_sync(self, image_data):
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Handle Transparency
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                bg = Image.new('RGB', image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = bg
            
            # Mask out specific UI elements (e.g., timestamps/buttons on the right)
            draw = ImageDraw.Draw(image)
            draw.rectangle([image.width - 80, 0, image.width, 75], fill=(255, 255, 255))
            
            # Upscale for better Tesseract reading
            if image.width < 600:
                image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                
            # Convert to grayscale and apply natural contrast
            image = image.convert('L') 
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0) 
            
            # Tesseract config: PSM 11 to scan for sparse text anywhere in the image
            custom_config = r"--psm 11"
            
            raw_ocr_text = pytesseract.image_to_string(image, config=custom_config)
            words = raw_ocr_text.split()
            
            cleaned_parts = []
            for word in words:
                if (word.startswith('<') and word.endswith('>')) or (word.startswith(':') and word.endswith(':')):
                    continue
                
                clean = self.alnum_regex.sub('', word)
                if len(clean) >= 3:
                    cleaned_parts.append(clean)
                    
            return " ".join(cleaned_parts[:3]) if cleaned_parts else None
            
        except Exception as e:
            print(f"{Colors.RED}[!] Error processing image bytes inside background thread: {e}{Colors.RESET}")
            return None

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
            
            # 1. Anti-Bot Verification Detection
            if f"Whoa there. Please tell us you're human! https://verify.poketwo.net/captcha/{self.user.id}" in content:
                link = f"https://verify.poketwo.net/captcha/{self.user.id}"
                blue_link = f"\033[34m\033]8;;{link}\033\\{link}\033]8;;\033\\{Colors.YELLOW}"
                
                print(f"\n{Colors.YELLOW}⚠ Pokétwo is requesting human verification, visit {blue_link} to verify your account then restart this bot. {Colors.RESET}")
                print(f"{Colors.RED}{Colors.BOLD}[-] Shutting down bot processes... 𐄂{Colors.RESET}")
                
                if self.session and not self.session.closed:
                    await self.session.close()
                await self.close()
                return

            # 2. Standard Logic
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
                            if "male" in gender_raw:
                                gender = f"{Colors.BLUE}♂{Colors.RESET}"
                            elif "female" in gender_raw:
                                gender = f"{Colors.MAGENTA}♀{Colors.RESET}"
                            elif "other" in gender_raw:
                                gender = "?"
                                
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] Caught a [{lvl}] {name} ({iv}% IV) {gender}! ☑{Colors.RESET}")
                    else:
                        print(f"{Colors.GREEN}{Colors.BOLD}[$$$] SUCCESS: {content} ☑{Colors.RESET}")
                self.sent_catch_attempt = False 
            return
            
        if message.author.id not in (self.target_user_1, self.target_user_2):
            return
            
        if message.guild:
            bot_permissions = message.channel.permissions_for(message.guild.me)
            if not bot_permissions.send_messages:
                return

        extracted_word = None
        
        if message.author.id == self.target_user_2:
            match = self.new_user_pattern.match(content)
            if match:
                extracted_word = match.group(1).strip()
                
        elif message.author.id == self.target_user_1 and content.startswith("##"):
            words = content[2:].strip().split()
            tag_index = next((i for i, w in enumerate(words) if (w.startswith('<') and w.endswith('>')) or (w.startswith(':') and w.endswith(':'))), -1)
            
            if tag_index > 0:
                target_words = words[:tag_index]
                cleaned_parts = [self.alnum_regex.sub('', w) for w in target_words if len(self.alnum_regex.sub('', w)) >= 3]
                if cleaned_parts:
                    extracted_word = " ".join(cleaned_parts[:3])
                    
            if not extracted_word and words:
                for word in words:
                    if (word.startswith('<') and word.endswith('>')) or (word.startswith(':') and word.endswith(':')):
                        continue
                    clean = self.alnum_regex.sub('', word)
                    if len(clean) >= 3:
                        extracted_word = clean
                        break

        if extracted_word:
            best_match = self.get_best_match(extracted_word)
            if best_match:
                response_msg = f"<@716390085896962058> c {best_match}"
                await message.channel.send(response_msg)
                print(f"{Colors.CYAN}[+] Sent (Text Match): {Colors.RESET}{Colors.BOLD}{response_msg}{Colors.RESET}")
                self.sent_catch_attempt = True 
            return 
        
        if message.author.id == self.target_user_1:
            image_url = None
            if message.attachments and message.attachments[0].content_type.startswith('image/'):
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
                    async with self.session.get(image_url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            
                            extracted_word = await asyncio.to_thread(self.process_image_sync, image_data)
                            
                            if extracted_word:
                                best_match = self.get_best_match(extracted_word)
                                if best_match:
                                    response_msg = f"<@716390085896962058> c {best_match}"
                                    await message.channel.send(response_msg)
                                    print(f"{Colors.CYAN}[+] Sent (OCR Match): {Colors.RESET}{Colors.BOLD}{response_msg}{Colors.RESET}")
                                    self.sent_catch_attempt = True
                            else:
                                print(f"{Colors.YELLOW}[-] No valid words found in OCR.{Colors.RESET}")
                except Exception as e:
                    print(f"{Colors.RED}[!] Error tracking processing image sequence: {e}{Colors.RESET}")

client = OcrSelfBot()
client.run("hidden")