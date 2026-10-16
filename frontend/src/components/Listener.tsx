import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';

type FeedState = 'live' | 'paused' | 'stopped';
// The listener view also has a Waiting state before the day's feed starts.
type ListenerState = 'waiting' | FeedState;

const WS_ORIGIN = 'ws://localhost:8000';
const PRIMER_TEXT = 'Audio active';

// Language codes on the wire, BCP 47 tags for the browser's voice engine.
const LANG_TAGS: Record<string, string> = {
  en: 'en-US',
  ko: 'ko-KR',
  'zh-hans': 'zh-CN',
  'zh-hant': 'zh-TW',
};

interface TranslationMessage {
  original: string;
  translation: string;
}

const LISTENER_STATE_UI: Record<ListenerState, { label: string; pill: string; dot: string }> = {
  waiting: {
    label: 'Waiting',
    pill: 'bg-slate-100 border-slate-300 text-slate-600',
    dot: 'bg-slate-400',
  },
  live: {
    label: 'Live',
    pill: 'bg-emerald-50 border-emerald-300 text-emerald-800',
    dot: 'bg-emerald-500 animate-pulse',
  },
  paused: {
    label: 'Paused',
    pill: 'bg-amber-50 border-amber-300 text-amber-800',
    dot: 'bg-amber-500',
  },
  stopped: {
    label: 'Ended',
    pill: 'bg-slate-100 border-slate-300 text-slate-600',
    dot: 'bg-slate-400',
  },
};

export default function Listener() {
  const { roomId, lang } = useParams<{ roomId: string; lang: string }>();
  const location = useLocation();
  const initialIsLive = (location.state as { isLive?: boolean } | null)?.isLive;

  const [listenerState, setListenerState] = useState<ListenerState>(
    initialIsLive === true ? 'live' : 'waiting'
  );
  const [messages, setMessages] = useState<TranslationMessage[]>([]);
  const [interimMessage, setInterimMessage] = useState<TranslationMessage | null>(null);
  const [isAudioEnabled, setIsAudioEnabled] = useState(false);

  // The WebSocket handler reads the live values through refs: it is created
  // once per connection and must not see stale audio/feed state.
  const audioEnabledRef = useRef(isAudioEnabled);
  const listenerStateRef = useRef(listenerState);
  const translationScrollRef = useRef<HTMLDivElement>(null);
  const japaneseScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    audioEnabledRef.current = isAudioEnabled;
  }, [isAudioEnabled]);

  useEffect(() => {
    listenerStateRef.current = listenerState;
  }, [listenerState]);

  const speak = useCallback(
    (text: string, volume = 1) => {
      const synth = window.speechSynthesis;
      if (!synth) return;

      const tag = LANG_TAGS[lang ?? ''] || lang || 'en-US';
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = tag;
      utterance.volume = volume;

      // Pick a voice for the guest's language, favouring higher-quality
      // system voices when the device exposes them.
      const voices = synth.getVoices();
      const prefix = tag.split('-')[0].toLowerCase();
      const matching = voices.filter((voice) =>
        voice.lang.toLowerCase().startsWith(prefix)
      );
      const preferred = matching.find(
        (voice) => voice.name.includes('Natural') || voice.name.includes('Google')
      );
      const voice = preferred || matching[0];
      if (voice) utterance.voice = voice;

      synth.speak(utterance);
    },
    [lang]
  );

  // Adjust state during render when the route moves to another room or
  // language: the panels must not carry lines from the previous connection.
  const connectionId = `${roomId}/${lang}`;
  const [activeConnection, setActiveConnection] = useState(connectionId);
  if (activeConnection !== connectionId) {
    setActiveConnection(connectionId);
    setMessages([]);
    setInterimMessage(null);
  }

  useEffect(() => {
    if (!roomId || !lang) return;

    const socket = new WebSocket(`${WS_ORIGIN}/ws/listen/${roomId}/${lang}`);

    socket.onmessage = (event) => {
      let payload: { type: string; data: unknown };
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      if (payload.type === 'history') {
        const history = payload.data as TranslationMessage[];
        setMessages(history.filter((msg) => msg && msg.original !== undefined));
        return;
      }

      if (payload.type === 'live_translation') {
        const message = payload.data as TranslationMessage;
        if (!message || message.original === undefined) return;
        setMessages((prev) => [...prev, message]);
        setInterimMessage(null);
        // Only a Waiting guest is promoted: after a Stop, stray in-flight
        // lines must not resurrect the feed until the operator restarts it.
        setListenerState((prev) => (prev === 'waiting' ? 'live' : prev));
        // Speak only while the feed is running; pause silences translations.
        if (audioEnabledRef.current && listenerStateRef.current !== 'paused' && listenerStateRef.current !== 'stopped') {
          speak(message.translation);
        }
        return;
      }

      if (payload.type === 'interim_translation') {
        const interim = payload.data as TranslationMessage;
        if (!interim || interim.original === undefined) return;
        setInterimMessage(interim);
        setListenerState((prev) => (prev === 'waiting' ? 'live' : prev));
        return;
      }

      if (payload.type === 'feed_state') {
        const state = payload.data;
        if (state === 'live' || state === 'paused' || state === 'stopped') {
          setListenerState(state);
          if (state !== 'live') {
            setInterimMessage(null);
            window.speechSynthesis?.cancel();
          }
          if (state === 'stopped') {
            setIsAudioEnabled(false);
          }
        }
      }
    };

    return () => socket.close();
  }, [roomId, lang, speak]);

  // A language change re-primes the voice engine with the new language so the
  // next line does not start in the previous voice.
  const previousLangRef = useRef(lang);
  useEffect(() => {
    if (previousLangRef.current === lang) return;
    previousLangRef.current = lang;
    window.speechSynthesis?.cancel();
    if (audioEnabledRef.current) speak(PRIMER_TEXT, 0.05);
  }, [lang, speak]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  // Follow the newest line only when the guest is already at the bottom, so
  // scrolling back to re-read a line is not interrupted mid-scroll.
  useEffect(() => {
    const NEAR_BOTTOM_PX = 120;
    for (const element of [translationScrollRef.current, japaneseScrollRef.current]) {
      if (!element) continue;
      const distanceFromBottom =
        element.scrollHeight - element.scrollTop - element.clientHeight;
      if (distanceFromBottom <= NEAR_BOTTOM_PX) {
        element.scrollTop = element.scrollHeight;
      }
    }
  }, [messages.length, interimMessage]);

  const toggleAudio = () => {
    if (isAudioEnabled) {
      window.speechSynthesis?.cancel();
      setIsAudioEnabled(false);
      return;
    }
    // The primer unlocks the browser's audio engine and warms the chosen voice.
    window.speechSynthesis?.cancel();
    speak(PRIMER_TEXT, 0.05);
    setIsAudioEnabled(true);
  };

  const audioAvailable = listenerState === 'live' || listenerState === 'paused';

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-12 h-screen flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-4 shrink-0">
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">Live Translation</h2>
        <div className="flex items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold tracking-wide uppercase ${LISTENER_STATE_UI[listenerState].pill}`}
          >
            <span className={`h-2 w-2 rounded-full ${LISTENER_STATE_UI[listenerState].dot}`} />
            {LISTENER_STATE_UI[listenerState].label}
          </span>
          <button
            onClick={toggleAudio}
            disabled={!audioAvailable}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold tracking-wide uppercase border transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed ${
              isAudioEnabled
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700 hover:bg-indigo-100'
                : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
            }`}
          >
            {isAudioEnabled ? (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15.536 8.464a5 5 0 010 7.072M17.657 6.343a8 8 0 010 11.314M5 10v4a2 2 0 002 2h2.586l3.707 3.707a1 1 0 001.707-.707V5a1 1 0 00-1.707-.707L9.586 10H7a2 2 0 00-2 2z" /></svg>
                Audio: ON
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" /></svg>
                Audio: OFF
              </>
            )}
          </button>
        </div>
      </div>

      {listenerState === 'paused' && (
        <div className="mb-4 shrink-0 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-center font-bold text-sm">
          Paused — worship music
        </div>
      )}
      {listenerState === 'stopped' && (
        <div className="mb-4 shrink-0 bg-slate-100 border border-slate-300 text-slate-600 rounded-xl px-4 py-3 text-center font-bold text-sm">
          Service ended
        </div>
      )}

      <div
        data-testid="panels"
        className="flex flex-col md:grid md:grid-cols-2 gap-4 md:gap-6 flex-1 min-h-0 overflow-hidden pb-4"
      >
        <div
          data-testid="japanese-panel"
          className="order-2 md:order-none bg-slate-100/70 border border-slate-200/60 rounded-xl flex flex-col min-h-0 flex-[2] md:flex-none overflow-hidden"
        >
          <div className="px-5 py-3.5 bg-slate-200/50 border-b border-slate-200 text-xs font-bold tracking-wider text-slate-500 uppercase shrink-0">
            日本語 (Transcript)
          </div>
          <div
            ref={japaneseScrollRef}
            data-testid="japanese-scroll"
            className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1"
          >
            {messages.map((msg, index) => (
              <div
                key={`ja-${index}`}
                className="bg-white p-4 rounded-xl border border-slate-200/50 shadow-xs text-slate-800 text-base leading-relaxed"
              >
                {msg.original}
              </div>
            ))}
            {interimMessage?.original && (
              <div className="bg-white/60 p-4 rounded-xl border border-dashed border-slate-300 shadow-xs text-slate-400 text-base leading-relaxed italic opacity-80">
                {interimMessage.original}
                <span className="inline-block w-1.5 h-4 bg-slate-400 animate-pulse ml-1 align-middle rounded-xs" />
              </div>
            )}
          </div>
        </div>

        <div
          data-testid="translation-panel"
          className="order-1 md:order-none bg-white border border-slate-200 rounded-xl flex flex-col min-h-0 flex-[3] md:flex-none overflow-hidden shadow-xs"
        >
          <div className="px-5 py-3.5 bg-indigo-50/50 border-b border-indigo-100 text-xs font-bold tracking-wider text-indigo-600 uppercase shrink-0">
            {lang?.toUpperCase()} (Translation)
          </div>
          <div
            ref={translationScrollRef}
            data-testid="translation-scroll"
            className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1"
          >
            {listenerState === 'waiting' && messages.length === 0 && (
              <div className="h-full flex items-center justify-center">
                <p className="text-center text-slate-500 font-medium">
                  Waiting for operator to start the feed…
                </p>
              </div>
            )}
            {messages.map((msg, index) => (
              <div
                key={`translation-${index}`}
                className="bg-slate-50 p-4 rounded-xl border-l-4 border-indigo-500 text-slate-900 text-base leading-relaxed shadow-2xs"
              >
                {msg.translation}
              </div>
            ))}
            {interimMessage?.translation && (
              <div className="bg-slate-50/50 p-4 rounded-xl border-l-4 border-dashed border-indigo-300 text-slate-500 text-base leading-relaxed italic opacity-75">
                {interimMessage.translation}
                <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-1 align-middle rounded-xs" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
