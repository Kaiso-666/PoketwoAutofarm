import discord
import re
import io
import aiohttp
import pytesseract
import asyncio
import difflib
from PIL import Image, ImageEnhance

# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OcrSelfBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None
        self.pokemon_dict = {}             
        self.pokemon_normalized_names = [] 
        
        # Target user IDs
        self.target_user_1 = 874910942490677270
        self.target_user_2 = 854233015475109888
        self.poketwo_id = 716390085896962058
        
        # ADDED: Guild ID exclusion list
        self.excluded_guilds = {1520755884693913703, 676767676767676767} 
        
        # Pre-compile regex patterns
        self.alnum_regex = re.compile(r"[^a-zA-Z0-9\-\']")
        self.normalization_regex = re.compile(r"[^a-z0-9]")
        self.new_user_pattern = re.compile(r"^([^:]+):\s*\d+%\s*$")
        
        # NEW: Pattern to extract Level, Name, Gender, and IVs from the success string
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
            print(f"[*] Loaded {len(self.pokemon_dict)} Pokémon names into memory.")
        except FileNotFoundError:
            print("[!] Warning: pokenames.txt not found. Matching will not work.")

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
            
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                bg = Image.new('RGB', image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = bg
            
            if image.width < 600:
                image = image.resize((image.width * 2, image.height * 2), Image.Resampling.BICUBIC)
                
            image = image.convert('L') 
            
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.5)
            
            custom_config = r"--psm 11 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
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
            print(f"[!] Error processing image bytes inside background thread: {e}")
            return None

    async def on_ready(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        print(f'[*] Logged in as {self.user}! Listening for messages...')

    async def on_message(self, message):
        # 1. Check for Guild Exclusion
        if message.guild and message.guild.id in self.excluded_guilds:
            return
            
        content = message.content.strip() if message.content else ""
        
        # --- Pokétwo Success / Fail Tracker ---
        if message.author.id == self.poketwo_id:
            if "That is the wrong pokémon!" in content:
                print("[-] Catch Failed: Incorrect Pokémon name guessed.")
            elif f"Congratulations <@{self.user.id}>!" in content:
                # NEW: Format regex mapping block
                match = self.success_pattern.search(content)
                if match:
                    lvl = match.group(1)
                    name = match.group(2).strip()
                    gender_raw = match.group(3)
                    iv = match.group(4)
                    
                    # Convert the Discord emoji strings to standard terminal icons
                    gender = ""
                    if gender_raw:
                        if "male" in gender_raw:
                            gender = " ♂️"
                        elif "female" in gender_raw:
                            gender = " ♀️"
                            
                    print(f"[$$$] Caught a [{lvl}] {name} ({iv}% IV){gender} !")
                else:
                    # Fallback just in case Pokétwo changes their message format slightly
                    print(f"[$$$] SUCCESS: {content}")
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
                print(f"[+] Sent (Text Match): {response_msg}")
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
                                    print(f"[+] Sent (OCR Match): {response_msg}")
                            else:
                                print("[-] No valid words found in OCR.")
                except Exception as e:
                    print(f"[!] Error tracking processing image sequence: {e}")

client = OcrSelfBot()
client.run("TOKEN_HERE")