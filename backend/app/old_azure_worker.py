import os
import asyncio
import httpx
import azure.cognitiveservices.speech as speechsdk
from app.socket_manager import manager

class AzureWorker:
    def __init__(self, room_id: str, loop: asyncio.AbstractEventLoop):
        self.room_id = room_id
        self.loop = loop
        
        self.master_queue = []
        self.lang_queues = {"en": [], "ko": [], "zh-hans": [], "zh-hant": []}
        
        self.languages = [
            ("English", "en"),
            ("Korean", "ko"),
            ("Simplified Chinese", "zh-hans"),
            ("Traditional Chinese", "zh-hant")
        ]
        
        # 1. AZURE SPEECH CONFIGURATION
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"), 
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        self.speech_config.speech_recognition_language = "ja-JP"

        self.audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
        self.push_stream = speechsdk.audio.PushAudioInputStream(stream_format=self.audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)

        self.recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)
        
        phrase_list = speechsdk.PhraseListGrammar.from_recognizer(self.recognizer)
        custom_words = [
            "イエス", "キリスト", "アーメン", "ハレルヤ", "メシア", "聖霊", "神様", "神", "聖書", "牧師", "祈り"
        ]
        for word in custom_words:
            phrase_list.addPhrase(word)

        # 2. GEMINI CONFIGURATION
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # 🔙 REVERTED TO FLASH: We know 100% this model works for your API key.
        # The extreme cost savings will come from the Noise Filter and Prompt Compression below.
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
        
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50)
        )
        
        self.running_tasks = []
        self.running_tasks.append(self.loop.create_task(self._master_distributor_loop()))
        for name, code in self.languages:
            self.running_tasks.append(self.loop.create_task(self._language_flusher_loop(name, code)))
            
        self._setup_callbacks()

    async def _queue_text(self, text: str):
        self.master_queue.append(text)

    async def _master_distributor_loop(self):
        """Pacing Stabilizer: Groups audio fragments every 4.0 seconds."""
        while True:
            await asyncio.sleep(4.0)
            if not self.master_queue:
                continue
                
            chunk_text = " ".join(self.master_queue)
            self.master_queue.clear()
            
            for code in self.lang_queues.keys():
                self.lang_queues[code].append(chunk_text)

    async def _language_flusher_loop(self, lang_name: str, lang_code: str):
        """Fast-Polling Track: Checks for work every 1.0s to eliminate lag, but only fires when text exists."""
        while True:
            await asyncio.sleep(1.0)
            queue = self.lang_queues[lang_code]
            
            if not queue:
                continue
                
            is_lagging = len(queue) > 1
            batch_text = " ".join(queue)
            
            # 💰 MONEY SAVER 1: Ultra-compressed 45-word prompt.
            prompt = f"Translate this Japanese sermon into {lang_name}. Fix Christian terms (seirei=Holy Spirit). "
            if is_lagging:
                prompt += "We are lagging. Paraphrase general preaching to catch up. Translate Bible verses strictly literally. "
            else:
                prompt += "Translate fully. Do not paraphrase. "
            prompt += "Output ONLY raw translated text."

            payload = {
                "systemInstruction": {"parts": [{"text": prompt}]},
                "contents": [{"parts": [{"text": batch_text}]}],
                "generationConfig": {"temperature": 0.1}
            }
            
            try:
                # 15s timeout gives ample safety headroom
                response = await self.http_client.post(self.gemini_url, json=payload, timeout=15.0)
                response.raise_for_status()
                
                translated_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                if translated_text:
                    self.lang_queues[lang_code].clear()
                    await manager.broadcast_to_language(batch_text, translated_text, self.room_id, lang_code)
                    
            except Exception as e:
                # 🐛 FIX: Print the ACTUAL HTTP status error so we never fly blind again.
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
                print(f"⚠️ [GEMINI LAG - {lang_name}] {type(e).__name__}: {error_msg}")

    def _setup_callbacks(self):
        def handled_recognized_event(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                japanese_text = evt.result.text
                
                # 💰 MONEY SAVER 2: The Noise Filter. 
                # Strips out punctuation. If nothing is left but filler, we ignore it completely.
                clean_text = japanese_text.replace("。", "").replace("、", "").replace(".", "").strip()
                
                if len(clean_text) > 0 and clean_text not in ["あ", "あの", "えー", "うーん", "ええと", "はい"]:
                    print(f"👂 [AZURE HEARD]: {japanese_text}")
                    asyncio.run_coroutine_threadsafe(
                        self._queue_text(japanese_text),
                        self.loop
                    )

        self.recognizer.recognized.connect(handled_recognized_event)

    def process_audio_chunk(self, chunk: bytes):
        self.push_stream.write(chunk)
        
    def start(self):
        print("🎙️ [AZURE]: Starting continuous speech recognition...")
        self.recognizer.start_continuous_recognition_async()

    def stop(self):
        print("🛑 [AZURE]: Stopping speech recognition...")
        self.recognizer.stop_continuous_recognition_async()
        self.loop.create_task(self._delayed_teardown())

    async def _delayed_teardown(self):
        await asyncio.sleep(5.0)
        print("🧹 [CLEANUP]: Safely closing all background language loops.")
        for task in self.running_tasks:
            task.cancel()
        await self.http_client.aclose()