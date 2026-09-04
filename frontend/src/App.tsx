import { useState, useEffect, useRef } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';

interface TranslationMessage {
  original: string;
  translation: string;
}

export default function App() {
  const navigate = useNavigate();

  // --- GLOBAL STATE ---
  const [roomInput, setRoomInput] = useState('church_central');
  const [targetLang, setTargetLang] = useState('en');
  const [messages, setMessages] = useState<TranslationMessage[]>([]);
  const [interimMessage, setInterimMessage] = useState<TranslationMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isAudioEnabled, setIsAudioEnabled] = useState(false);
  
  // Trapdoor ref so the WebSocket can read the live state of the audio toggle
  const audioEnabledRef = useRef(isAudioEnabled);
  useEffect(() => {
    audioEnabledRef.current = isAudioEnabled;
  }, [isAudioEnabled]);

  // --- REFS ---
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const processor = useRef<ScriptProcessorNode | null>(null);
  const globalStream = useRef<MediaStream | null>(null);
  
  const originalContainerRef = useRef<HTMLDivElement | null>(null);
  const translationContainerRef = useRef<HTMLDivElement | null>(null);

  // --- SMART SCROLL ---
  const scrollToBottom = (container: HTMLDivElement | null) => {
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 150;
    if (isNearBottom) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom(originalContainerRef.current);
    scrollToBottom(translationContainerRef.current);
  }, [messages.length]);

  // --- WEBSOCKET CONNECTION (LISTENER) ---
  const connectListenerWebSocket = (roomId: string, lang: string) => {
    if (ws.current) ws.current.close();

    const wsUrl = `ws://localhost:8000/ws/listen/${roomId}/${lang}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => console.log("📡 Connected to Live Translation Room");
    
    ws.current.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'live_translation') {
          if (payload.data && payload.data.original !== undefined) {
            setMessages((prev) => [...prev, payload.data]);
            setInterimMessage(null);
            
            // Plain Text-to-Speech
            if (audioEnabledRef.current && window.speechSynthesis) {
              const synth = window.speechSynthesis;
              const utterance = new SpeechSynthesisUtterance(payload.data.translation);
              const voices = synth.getVoices();

              const langMap: Record<string, string> = {
                'en': 'en-US',
                'ko': 'ko-KR',
                'zh-hans': 'zh-CN',
                'zh-hant': 'zh-TW'
              };
              const targetLang = langMap[lang] || lang;
              utterance.lang = targetLang; 

              if (voices.length > 0) {
                const matchingLanguages = voices.filter(v => 
                  v.lang.toLowerCase().startsWith(targetLang.split('-')[0].toLowerCase())
                );
                if (matchingLanguages.length > 0) {
                  const preferredVoice = matchingLanguages.find(v => 
                    v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("Premium")
                  );
                  utterance.voice = preferredVoice || matchingLanguages[0];
                }
              }
              
              // Slightly lower pitch and speed makes AI voices sound more natural
              utterance.rate = 1.2; 
              synth.speak(utterance);
            }
          }
        } else if (payload.type === 'history') {
          const validHistory = payload.data.filter((msg: any) => msg && msg.original !== undefined);
          setMessages(validHistory);
        }
      } catch (e) {
        console.error("Malformed socket data:", e);
      }
    };

    ws.current.onclose = () => console.log("🔌 Disconnected from Room");
  };

  // --- AUDIO STREAMING ENGINE (PREACHER) ---
  const startAudioStreaming = async (roomId: string) => {
    try {
      const wsUrl = `ws://localhost:8000/ws/stream/${roomId}`;
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = async () => {
        console.log("🎙️ Audio Stream Socket Opened");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        globalStream.current = stream;

        audioContext.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.current.createMediaStreamSource(stream);
        
        processor.current = audioContext.current.createScriptProcessor(4096, 1, 1);
        source.connect(processor.current);
        processor.current.connect(audioContext.current.destination);

        processor.current.onaudioprocess = (e) => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              pcm16[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
            }
            ws.current.send(pcm16.buffer);
          }
        };
        setIsStreaming(true);
      };
    } catch (err) {
      console.error("Microphone access failed:", err);
      alert("Please allow microphone permissions to broadcast.");
    }
  };

  const stopAudioStreaming = () => {
    processor.current?.disconnect();
    audioContext.current?.close();
    globalStream.current?.getTracks().forEach(track => track.stop());
    ws.current?.close();
    setIsStreaming(false);
  };

  // --- ROUTING HANDLERS ---
  const handleJoinAsListener = () => {
    connectListenerWebSocket(roomInput, targetLang);
    navigate('/listener');
  };

  const handleJoinAsPreacher = () => {
    navigate('/preacher');
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased font-sans selection:bg-indigo-100 selection:text-indigo-900">
      <Routes>
        
        {/* VIEW 1: LANDING / PORTAL SELECTOR */}
        <Route path="/" element={
          <div className="flex items-center justify-center min-h-screen p-4">
            <div className="bg-white rounded-3xl shadow-2xl p-8 sm:p-12 w-full max-w-md border border-slate-100">
              <div className="text-center mb-10">
                <h1 className="text-5xl font-black tracking-tight text-indigo-600 mb-3 drop-shadow-sm">絆 KIZUNA</h1>
                <p className="text-sm text-slate-500 font-bold uppercase tracking-widest">Real-time Translation Hub</p>
              </div>

              <div className="space-y-8">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Church / Room ID</label>
                  <input 
                    type="text" 
                    value={roomInput}
                    onChange={(e) => setRoomInput(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all font-mono font-medium text-slate-700"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-6 border-t border-slate-100">
                  {/* Left Column: Listen */}
                  <div className="space-y-3">
                    <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                      Listen In
                    </span>
                    <select 
                      value={targetLang}
                      onChange={(e) => setTargetLang(e.target.value)}
                      className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      <option value="en">English (US)</option>
                      <option value="ko">한국어 (Korean)</option>
                      <option value="zh-hant">繁體中文 (Traditional)</option>
                      <option value="zh-hans">简体中文 (Simplified)</option>
                    </select>
                    <button 
                      onClick={handleJoinAsListener}
                      className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold rounded-xl transition-all shadow-lg shadow-indigo-200 text-sm"
                    >
                      Join Feed
                    </button>
                  </div>

                  {/* Right Column: Broadcast */}
                  <div className="space-y-3 flex flex-col justify-between">
                    <div>
                      <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2 mb-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                        Broadcaster
                      </span>
                      <p className="text-xs text-slate-500 leading-relaxed font-medium">Stream stage audio directly to Gemini Translation arrays.</p>
                    </div>
                    <button 
                      onClick={handleJoinAsPreacher}
                      className="w-full py-3 bg-slate-800 hover:bg-slate-900 active:bg-black text-white font-bold rounded-xl transition-all shadow-lg shadow-slate-300 text-sm"
                    >
                      Dashboard
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        } />

        {/* VIEW 2: PREACHER DASHBOARD */}
        <Route path="/preacher" element={
          <div className="max-w-3xl mx-auto pt-10 sm:pt-20 px-4">
            <div className="bg-white rounded-3xl shadow-xl p-6 sm:p-10 border border-slate-100">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                <div>
                  <button onClick={() => { stopAudioStreaming(); navigate('/'); }} className="text-sm font-bold text-slate-400 hover:text-indigo-600 mb-2 block transition-colors">
                    ← Return to Hub
                  </button>
                  <h2 className="text-3xl font-black text-slate-900 tracking-tight">Preacher Console</h2>
                  <p className="text-sm text-slate-500 font-mono mt-1 bg-slate-100 inline-block px-2 py-1 rounded">Channel: {roomInput}</p>
                </div>
                
                {/* Status Indicator */}
                <div className={`flex items-center gap-3 px-4 py-2 rounded-full border ${isStreaming ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-50 border-slate-200 text-slate-500'} shadow-sm font-bold tracking-wide uppercase text-xs`}>
                  <span className={`h-2.5 w-2.5 rounded-full ${isStreaming ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                  {isStreaming ? 'Live Broadcasting' : 'Offline'}
                </div>
              </div>

              <div className="p-8 sm:p-12 bg-slate-50 rounded-2xl border border-slate-200 text-center space-y-6">
                <div className="inline-block p-4 bg-white rounded-full shadow-sm mb-2">
                  <svg className={`w-8 h-8 ${isStreaming ? 'text-emerald-500' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                </div>
                <p className="text-base text-slate-600 max-w-md mx-auto font-medium">
                  Ensure your physical audio inputs are correct. Toggling transmission begins immediate low-latency streaming to the AI processing engine.
                </p>
                
                {!isStreaming ? (
                  <button 
                    onClick={() => startAudioStreaming(roomInput)}
                    className="px-8 py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl shadow-xl shadow-emerald-200/50 transition-all transform active:scale-95 text-lg"
                  >
                    Start Live Sermon
                  </button>
                ) : (
                  <button 
                    onClick={stopAudioStreaming}
                    className="px-8 py-4 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl shadow-xl shadow-rose-200/50 transition-all transform active:scale-95 text-lg"
                  >
                    Mute / End Stream
                  </button>
                )}
              </div>
            </div>
          </div>
        } />

        {/* VIEW 3: GUEST LISTENER VIEW */}
        <Route path="/listener" element={
          <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 h-screen flex flex-col">
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 shrink-0 bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-slate-100">
              
              {/* Left Side: Navigation & Title */}
              <div>
                <button onClick={() => { ws.current?.close(); setMessages([]); setInterimMessage(null); navigate('/'); }} className="text-sm font-bold text-slate-400 hover:text-indigo-600 mb-1 block transition-colors">
                  ← Exit Room
                </button>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight capitalize">{roomInput.replace('_', ' ')}</h2>
                  <span className="px-2.5 py-1 bg-indigo-100 text-indigo-700 text-xs font-bold rounded-md uppercase tracking-wider">
                    {targetLang}
                  </span>
                </div>
              </div>
              
              {/* Right Side: Status & Controls */}
              <div className="flex flex-row sm:flex-col items-center sm:items-end gap-3 w-full sm:w-auto justify-between sm:justify-end">
                
                <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-100 px-3 py-1.5 rounded-full text-emerald-700 text-[10px] sm:text-xs font-bold tracking-wide uppercase shadow-sm">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
                  Live Feed
                </div>
                
                <button
                  onClick={() => {
                    const newState = !isAudioEnabled;
                    setIsAudioEnabled(newState);
                    
                    if (newState && window.speechSynthesis) {
                      window.speechSynthesis.cancel();
                      const primer = new SpeechSynthesisUtterance("Audio active");
                      primer.volume = 0.01; 
                      window.speechSynthesis.speak(primer);
                    }
                  }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold tracking-wide uppercase border transition-all shadow-sm ${
                    isAudioEnabled
                      ? 'bg-indigo-50 border-indigo-200 text-indigo-700 hover:bg-indigo-100'
                      : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {isAudioEnabled ? (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15.536 8.464a5 5 0 010 7.072M17.657 6.343a8 8 0 010 11.314M18.364 5.636a9 9 0 010 12.728M5 10v4a2 2 0 002 2h2.586l3.707 3.707a1 1 0 001.707-.707V5a1 1 0 00-1.707-.707L9.586 10H7a2 2 0 00-2 2z" /></svg>
                      Audio: ON
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" clipRule="evenodd" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" /></svg>
                      Audio: OFF
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Split Screen Columns */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 flex-1 min-h-0 overflow-hidden pb-4 sm:pb-6">
              
              {/* 🐛 BUG FIX: The ref here was previously originalContainerRef by mistake. It is now correct. */}
              {/* Translation Output (Primary Focus) */}
              <div className="bg-white border border-slate-200 rounded-2xl flex flex-col h-full overflow-hidden shadow-sm order-1 md:order-2">
                <div className="px-5 py-4 bg-indigo-50/80 border-b border-indigo-100 text-xs font-black tracking-widest text-indigo-600 uppercase shrink-0 flex items-center justify-between">
                  <span>{targetLang} (Translation)</span>
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                  </span>
                </div>
                
                {/* Tailwind Custom Scrollbar classes added via inline or require index.css config */}
                <div ref={translationContainerRef} className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1 scroll-smooth">
                  {messages.length === 0 && !interimMessage && (
                    <div className="h-full flex items-center justify-center text-slate-400 font-medium text-sm">
                      Waiting for speaker to begin...
                    </div>
                  )}
                  {messages.map((msg, idx) => (
                    <div key={`trans-${idx}`} className="bg-slate-50 p-5 rounded-2xl border-l-4 border-indigo-500 text-slate-900 text-lg font-medium leading-relaxed shadow-sm transition-all duration-300">
                      {msg?.translation}
                    </div>
                  ))}
                  {interimMessage?.translation && (
                    <div className="bg-slate-50/50 p-5 rounded-2xl border-l-4 border-dashed border-slate-300 text-slate-500 text-lg font-medium leading-relaxed italic opacity-80 animate-pulse">
                      {interimMessage.translation} <span className="text-slate-400">...</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Japanese Original (Secondary) */}
              <div className="bg-slate-100/50 border border-slate-200/60 rounded-2xl flex flex-col h-full overflow-hidden order-2 md:order-1 hidden sm:flex">
                <div className="px-5 py-4 bg-slate-200/50 border-b border-slate-200 text-xs font-black tracking-widest text-slate-500 uppercase shrink-0">
                  日本語 (Original)
                </div>
                <div ref={originalContainerRef} className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1 scroll-smooth">
                  {messages.map((msg, idx) => (
                    <div key={`ja-${idx}`} className="bg-white p-5 rounded-2xl border border-slate-200/50 shadow-sm text-slate-700 text-base font-medium leading-relaxed">
                      {msg?.original}
                    </div>
                  ))}
                  {interimMessage?.original && (
                    <div className="bg-white/60 p-5 rounded-2xl border border-dashed border-slate-300 shadow-sm text-slate-400 text-base font-medium leading-relaxed italic opacity-80 animate-pulse">
                      {interimMessage.original} <span className="text-indigo-400 font-bold">...</span>
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>
        } />
      </Routes>
    </div>
  );
}