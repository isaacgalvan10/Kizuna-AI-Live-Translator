import json
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, dict[str, list[WebSocket]]] = {}
        self.history_buffer: dict[str, dict[str, list[dict]]] = {}

    def get_active_languages(self, room_id: str) -> list[str]:
        """Returns a list of language codes that currently have active listeners."""
        if room_id not in self.active_connections:
            return []
        
        active_langs = []
        for lang, websockets in self.active_connections[room_id].items():
            if len(websockets) > 0:
                active_langs.append(lang)
        return active_langs

    async def connect(self, websocket: WebSocket, room_id: str, language: str):
        await websocket.accept()
        
        # Safe initialization using setdefault: Never overwrites existing keys
        self.active_connections.setdefault(room_id, {})
        self.active_connections[room_id].setdefault(language, [])
        self.active_connections[room_id][language].append(websocket)
        
        self.history_buffer.setdefault(room_id, {})
        self.history_buffer[room_id].setdefault(language, [])

        # Broadcast the historical timeline to the reconnected client
        past_messages = self.history_buffer[room_id][language]
        if past_messages:
            payload = json.dumps({"type": "history", "data": past_messages})
            await websocket.send_text(payload)

    def disconnect(self, websocket: WebSocket, room_id: str, language: str):
        if room_id in self.active_connections and language in self.active_connections[room_id]:
            # Added a safe check to see if the websocket is actually still in the list
            if websocket in self.active_connections[room_id][language]:
                self.active_connections[room_id][language].remove(websocket)
            
            # Clean up empty dictionaries to save server memory
            if not self.active_connections[room_id][language]:
                del self.active_connections[room_id][language]

    async def broadcast_to_language(self, original: str, translation: str, room_id: str, language: str):
        message_obj = {"original": original, "translation": translation}
        
        # Always secure the history state safely
        self.history_buffer.setdefault(room_id, {})
        self.history_buffer[room_id].setdefault(language, [])
        self.history_buffer[room_id][language].append(message_obj)
            
        if room_id in self.active_connections and language in self.active_connections[room_id]:
            payload = json.dumps({"type": "live_translation", "data": message_obj})
            dead_connections = []
            
            for connection in self.active_connections[room_id][language]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)
            
            for dead in dead_connections:
                self.disconnect(dead, room_id, language)

    async def broadcast_interim(self, original: str, translation: str, room_id: str, language: str):
        if room_id in self.active_connections and language in self.active_connections[room_id]:
            payload = json.dumps({
                "type": "interim_translation", 
                "data": {"original": original, "translation": translation}
            })
            dead_connections = []
            
            for connection in self.active_connections[room_id][language]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)
                    
            for dead in dead_connections:
                self.disconnect(dead, room_id, language)

manager = ConnectionManager()