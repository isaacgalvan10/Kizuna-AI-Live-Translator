import os
import asyncio
import base64
import io
import wave
import json
import re
import httpx
from app.socket_manager import manager

class GeminiWorker:
    def __init__(self, room_id: str, loop: asyncio.AbstractEventLoop):
        self.room_id = room_id
        self.loop = loop
        
        self.audio_buffer = bytearray()
        self.buffer_lock = asyncio.Lock()
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        # Ensure we are using the highly capable 2.5 Flash model
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
        
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
        
        self.is_running = True
        self.flusher_task = self.loop.create_task(self._audio_flusher_loop())

        # Map frontend language codes to prompt instructions
        self.lang_map = {
            "en": ("[EN]", "English translation"),
            "ko": ("[KO]", "Korean translation"),
            "zh-hans": ("[ZH-HANS]", "Simplified Chinese translation"),
            "zh-hant": ("[ZH-HANT]", "Traditional Chinese translation")
        }

    def process_audio_chunk(self, chunk: bytes):
        self.audio_buffer.extend(chunk)

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate=16000, sample_width=2, channels=1) -> bytes:
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return wav_io.getvalue()

    async def _audio_flusher_loop(self):
        while self.is_running:
            await asyncio.sleep(3.5)
            
            active_langs = manager.get_active_languages(self.room_id)
            
            async with self.buffer_lock:
                if len(self.audio_buffer) < 32000:
                    continue
                
                if not active_langs:
                    self.audio_buffer.clear()
                    continue
                    
                raw_pcm = bytes(self.audio_buffer)
                self.audio_buffer.clear()

            expected_tags = []
            translation_targets = []
            output_format_str = "[JA] <Japanese transcription>\n"
            
            for code in active_langs:
                if code in self.lang_map:
                    tag, description = self.lang_map[code]
                    expected_tags.append((code, tag))
                    translation_targets.append(description)
                    output_format_str += f"{tag} <{description}>\n"

            # 🚀 ENHANCED PROMPT: Strict rules for filtering Japanese speech fillers and non-essential 'はい'
            dynamic_prompt = f"""You are a real-time speech-to-text and multi-language translator for a Japanese Christian church sermon.

INSTRUCTIONS:
1. Listen carefully to the Japanese audio stream.
2. Transcribe the spoken Japanese text into clean, natural Japanese.
3. FILTER OUT ALL FILLER WORDS: Omit hesitation sounds, stutters, and verbal fillers (e.g., 'え', 'えっと', 'あの', 'うーん', 'ええと', 'まあ', 'ね').
4. FILTER OUT NON-ESSENTIAL AFFIRMATION: Omit standalone 'はい', 'うん', or 'そう' when spoken as natural pauses, breathing fillers, or conversational acknowledgements. ONLY include 'はい' if it is a meaningful answer to a direct question or a key part of an actual sentence.
5. Translate the cleaned text into: {', '.join(translation_targets)}.
6. Correct phonetic STT errors based on Christian context (e.g., 'seirei' -> Holy Spirit / 聖霊).
7. If the audio is Bible reading, translate strictly word-for-word. If general preaching, translate naturally without fillers.
8. If the audio chunk contains ONLY filler words, silence, or noise, leave all tags blank.

OUTPUT FORMAT (Output ONLY these tagged blocks, no markdown code blocks):
{output_format_str}"""

            wav_bytes = self._pcm_to_wav(raw_pcm)
            base64_audio = base64.b64encode(wav_bytes).decode('utf-8')

            payload = {
                "systemInstruction": {"parts": [{"text": dynamic_prompt}]},
                "contents": [{
                    "parts": [
                        {"inlineData": {"mimeType": "audio/wav", "data": base64_audio}},
                        {"text": "Transcribe and translate this Japanese sermon audio chunk."}
                    ]
                }],
                "generationConfig": {"temperature": 0.1}
            }

            try:
                response = await self.http_client.post(self.gemini_url, json=payload, timeout=15.0)
                response.raise_for_status()

                response_json = response.json()
                candidates = response_json.get("candidates", [])
                if not candidates or "content" not in candidates[0]:
                    continue

                raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                parsed_results = self._parse_dynamic_response(raw_text, expected_tags)

                japanese_text = parsed_results.get("ja", "")
                
                # If Gemini filtered out all filler words and nothing meaningful remains, skip broadcasting
                if japanese_text and len(japanese_text) > 1:
                    print(f"🎙️ [GEMINI HEARD]: {japanese_text}")
                    for code, _ in expected_tags:
                        translated_text = parsed_results.get(code, "")
                        if translated_text:
                            await manager.broadcast_to_language(japanese_text, translated_text, self.room_id, code)

            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
                print(f"⚠️ [GEMINI AUDIO ERROR] {type(e).__name__}: {error_msg}")

    def _parse_dynamic_response(self, text: str, expected_tags: list) -> dict:
        """Parses [JA] and dynamically requested language tags from Gemini output."""
        parsed = {}
        
        # Always parse Japanese original
        ja_match = re.search(r"\[JA\]\s*(.*?)(?=\[|$)", text, re.DOTALL | re.IGNORECASE)
        parsed["ja"] = ja_match.group(1).strip() if ja_match else ""

        # Dynamically parse requested languages
        for code, tag in expected_tags:
            pattern = rf"\{tag}\s*(.*?)(?=\[|$)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            parsed[code] = match.group(1).strip() if match else ""
            
        return parsed

    def start(self):
        print("🎙️ [GEMINI WORKER]: Audio stream worker started...")

    def stop(self):
        print("🛑 [GEMINI WORKER]: Stopping worker...")
        self.is_running = False
        if hasattr(self, 'flusher_task'):
            self.flusher_task.cancel()
        self.loop.create_task(self.http_client.aclose())