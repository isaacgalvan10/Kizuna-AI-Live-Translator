import os
import array
import math
import asyncio
import base64
import io
import wave
import re
import httpx
from app.socket_manager import manager

# 16-bit mono PCM at 16kHz is 32,000 bytes per second.
MIN_BUFFER_BYTES = int(32000 * 1.5)
MAX_BUFFER_BYTES = int(32000 * 5.0)

# Loudness gate: RMS of a 1.5s chunk, on the 16-bit scale (0-32767).
# Silence and room tone measure well under this; clear speech measures in the
# thousands. Chunks below it are dropped WITHOUT asking Gemini, because a
# language model handed a no-speech chunk tends to invent plausible sermon
# content ("Now, I will read from the Scripture.") instead of staying silent.
# Override with MIN_SPEECH_RMS for tuning.
DEFAULT_MIN_SPEECH_RMS = 200

# Ways a model can report "nothing was said" instead of a transcription.
SILENCE_MARKERS = {"silence", "no speech", "no audible speech"}


class GeminiWorker:
    def __init__(self, room_id: str, loop: asyncio.AbstractEventLoop):
        self.room_id = room_id
        self.loop = loop
        
        self.audio_buffer = bytearray()
        self.buffer_lock = asyncio.Lock()
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
        self.min_speech_rms = int(os.getenv("MIN_SPEECH_RMS", str(DEFAULT_MIN_SPEECH_RMS)))
        
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
        
        self.is_running = True
        self.flusher_task = self.loop.create_task(self._audio_flusher_loop())

        self.lang_map = {
            "en": ("[EN]", "English translation"),
            "ko": ("[KO]", "Korean translation"),
            "zh-hans": ("[ZH-HANS]", "Simplified Chinese translation"),
            "zh-hant": ("[ZH-HANT]", "Traditional Chinese translation")
        }

    def process_audio_chunk(self, chunk: bytes):
        """Appends raw PCM audio bytes to the buffer in real time."""
        self.audio_buffer.extend(chunk)

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate=16000, sample_width=2, channels=1) -> bytes:
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return wav_io.getvalue()

    def _pcm_rms(self, pcm_bytes: bytes) -> float:
        """Root-mean-square loudness of 16-bit little-endian PCM, or 0.0 for silence."""
        usable = len(pcm_bytes) - (len(pcm_bytes) % 2)
        if usable == 0:
            return 0.0
        samples = array.array("h")
        samples.frombytes(pcm_bytes[:usable])
        return math.sqrt(sum(float(s) * s for s in samples) / len(samples))

    def _is_silence_marker(self, text: str) -> bool:
        """True when the model answered with a bare 'nothing was said' marker."""
        normalized = text.strip().strip("[](){}<>!.。!！").strip().lower()
        return normalized in SILENCE_MARKERS

    async def _audio_flusher_loop(self):
        while self.is_running:
            await asyncio.sleep(3.0)
            await self._flush_cycle()

    async def _flush_cycle(self):
        try:
            # 🛑 SAFETY CHECK: Ensure socket_manager was actually updated properly
            if not hasattr(manager, 'get_active_languages'):
                print("❌ [FATAL ERROR]: socket_manager.py is missing the 'get_active_languages' function!")
                return

            active_langs = manager.get_active_languages(self.room_id)
            buffer_size = len(self.audio_buffer)

            # 📊 DIAGNOSTIC PRINT 1: Tells us if the rooms match and if audio is arriving
            print(f"📊 [DIAGNOSTIC] Room: '{self.room_id}' | Listeners: {active_langs} | Audio: {buffer_size} bytes")

            async with self.buffer_lock:
                if not active_langs:
                    self.audio_buffer.clear()
                    return

                if len(self.audio_buffer) < MIN_BUFFER_BYTES:
                    print(f"⏳ [WAITING] Buffer too small ({len(self.audio_buffer)} < {MIN_BUFFER_BYTES}). Waiting for more audio...")
                    return

                chunk_size = min(len(self.audio_buffer), MAX_BUFFER_BYTES)
                raw_pcm = bytes(self.audio_buffer[:chunk_size])
                del self.audio_buffer[:chunk_size]

            # 👇 ADD THIS LINE TO CHECK FOR A DEAD MIC
            print(f"🎤 [MIC CHECK]: Non-zero bytes: {sum(1 for b in raw_pcm if b != 0)} / {len(raw_pcm)}")

            rms = self._pcm_rms(raw_pcm)
            print(f"🔊 [LOUDNESS]: RMS {rms:.0f} (gate: {self.min_speech_rms})")
            if rms < self.min_speech_rms:
                print("🔇 [SILENCE GATE]: No audible speech in this chunk; skipping the Gemini call.")
                return

            expected_tags = []
            translation_targets = []
            output_format_str = "[JA] <Japanese transcription>\n"
            
            for code in active_langs:
                if code in self.lang_map:
                    tag, description = self.lang_map[code]
                    expected_tags.append((code, tag))
                    translation_targets.append(description)
                    output_format_str += f"{tag} <{description}>\n"

            dynamic_prompt = f"""You are an elite real-time multi-language interpreter for a Japanese Christian church sermon.
            TASK:
            1. Listen to the Japanese audio.
            2. Transcribe clean Japanese into [JA].
            3. FILTER OUT ALL FILLER WORDS: Omit hesitation sounds, stutters, and verbal fillers (e.g., 'え', 'えっと', 'あの', 'うーん', 'ええと', 'まあ', 'ね').
            4. FILTER OUT NON-ESSENTIAL AFFIRMATION: Omit standalone 'はい', 'うん', or 'そう' when spoken as natural pauses, breathing fillers, or conversational acknowledgements. ONLY include 'はい' if it is a meaningful answer to a direct question or a key part of an actual sentence.
            5. Translate into target languages: {', '.join(translation_targets)}.

            HALLUCINATION GUARD (CRITICAL):
            - Transcribe ONLY words that are clearly audible in the audio. Never invent, guess, complete, or smooth over content.
            - If the audio contains no clearly audible Japanese speech (silence, room tone, air conditioning, music, humming, applause), respond with exactly: [SILENCE] and nothing else.
            - Never generate plausible sermon phrases (greetings, scripture announcements, transitions) unless they were actually spoken in the audio.

            THEOLOGICAL GLOSSARY & CONTEXT:
            - 恵み (Megumi) -> Grace | 救い (Sukui) -> Salvation | 十字架 (Jūjika) -> Cross
            - 礼拝 (Reihai) -> Worship / Service | 聖霊 (Seirei) -> Holy Spirit | 復活 (Fukkatsu) -> Resurrection
            - 福音 (Fukuin) -> Gospel | 祈り (Inori) -> Prayer | 牧師 (Bokushi) -> Pastor / Minister
            - 神様 (Kamisama) -> God | 主 (Shu) -> The Lord | 聖書 (Seisho) -> The Bible / Scripture

            TRANSLATION QUALITY RULES:
            - Style: Fluent, warm, pastoral tone suitable for church worship.
            - Japanese SOV Handling: Read complete thoughts before translating so verbs and intent are accurate.
            - Scripture / Bible Verse Readings: Translate word-for-word with high biblical accuracy.
            - Incomplete Sentences: If the speaker pauses mid-thought, translate the fragment naturally without guessing or inventing unsaid information.

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

            print(f"🚀 [SENDING] Triggering Gemini API with {chunk_size} bytes of audio...")

            response = await self.http_client.post(self.gemini_url, json=payload, timeout=20.0)
            response.raise_for_status()

            response_json = response.json()
            candidates = response_json.get("candidates", [])
            if not candidates or "content" not in candidates[0]:
                print("⚠️ [GEMINI] Returned a completely empty response block.")
                return

            raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
            
            # 📥 DIAGNOSTIC PRINT 2: Let's see exactly what Google is generating before the regex touches it
            print(f"📥 [GEMINI RAW OUTPUT]:\n{raw_text}")
            print("-" * 30)

            parsed_results = self._parse_dynamic_response(raw_text, expected_tags)
            japanese_text = parsed_results.get("ja", "")

            if self._is_silence_marker(japanese_text):
                print("🔇 [SILENCE MARKER]: Gemini reported no meaningful speech; nothing broadcast.")
                return

            if japanese_text and len(japanese_text) > 1:
                print(f"✅ [BROADCASTING]: {japanese_text}")
                for code, _ in expected_tags:
                    translated_text = parsed_results.get(code, "")
                    if translated_text:
                        await manager.broadcast_to_language(japanese_text, translated_text, self.room_id, code)

        except httpx.HTTPStatusError as e:
            # HTTP errors usually mean bad API keys or model names
            error_msg = e.response.text if hasattr(e, 'response') else str(e)
            print(f"❌ [API REJECTED] {e.response.status_code}: {error_msg}")
        except Exception as e:
            # Catch absolutely everything else (like timeouts) and retry the audio
            async with self.buffer_lock:
                if 'raw_pcm' in locals():
                    self.audio_buffer = bytearray(raw_pcm) + self.audio_buffer
            print(f"⚠️ [LOOP CRASH CAUGHT] {type(e).__name__}: {str(e)}")
    
    def _parse_dynamic_response(self, text: str, expected_tags: list) -> dict:
        parsed = {}
        ja_match = re.search(r"\[JA\]\s*(.*?)(?=\[|$)", text, re.DOTALL | re.IGNORECASE)
        parsed["ja"] = ja_match.group(1).strip() if ja_match else ""

        for code, tag in expected_tags:
            tag_clean = tag.strip("[]")
            pattern = rf"\[{tag_clean}\]\s*(.*?)(?=\[|$)"
            
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
