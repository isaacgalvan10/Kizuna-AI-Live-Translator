import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { WS_ORIGIN } from '../ws';
import { LISTENER_STATE_VISUALS } from '../feedStateVisuals';
import type { ListenerState } from '../feedStateVisuals';

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
  const stateVisuals = LISTENER_STATE_VISUALS[listenerState];

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-12 h-screen flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-4 shrink-0 px-1 pt-0.5 pb-3.5 border-b border-line-soft">
        <h2 className="text-[16px] font-bold text-ink tracking-[0.01em]">Live Translation</h2>
        <div className="flex items-center gap-2">
          <span
            role="status"
            aria-live="polite"
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold tracking-[0.07em] uppercase shadow-float ${stateVisuals.pill}`}
          >
            <span className={`h-2 w-2 rounded-full ${stateVisuals.dot}`} />
            {stateVisuals.label}
          </span>
          <button
            onClick={toggleAudio}
            disabled={!audioAvailable}
            aria-pressed={isAudioEnabled}
            className={`flex items-center gap-2 rounded-full border px-[13px] py-[7px] text-[11px] font-bold tracking-[0.07em] uppercase cursor-pointer transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed ${
              isAudioEnabled
                ? 'bg-brand-wash border-brand-line text-brand-deep hover:bg-brand-line/60'
                : 'bg-sand-raise border-line text-dim hover:bg-sand-hover'
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
        <div className="mb-4 shrink-0 rounded-xl border border-paused-line bg-paused-soft px-4 py-2.5 text-center text-[13.5px] font-bold text-paused-ink">
          Paused — worship music
        </div>
      )}
      {listenerState === 'stopped' && (
        <div className="mb-4 shrink-0 rounded-xl border border-stopped-line bg-stopped-soft px-4 py-2.5 text-center text-[13.5px] font-bold text-stopped-ink">
          Service ended
        </div>
      )}

      <div
        data-testid="panels"
        className="flex flex-col md:grid md:grid-cols-2 gap-4 md:gap-6 flex-1 min-h-0 overflow-hidden pb-4"
      >
        <div
          data-testid="japanese-panel"
          className="order-2 md:order-none bg-sand-panel border border-line-soft rounded-[14px] flex flex-col min-h-0 flex-[2] md:flex-none overflow-hidden"
        >
          <div className="px-[22px] py-3 border-b border-line-soft text-[10.5px] font-bold tracking-[0.14em] text-dim uppercase shrink-0">
            日本語 (Transcript)
          </div>
          <div
            ref={japaneseScrollRef}
            data-testid="japanese-scroll"
            className="px-5 sm:px-[26px] py-[22px] overflow-y-auto flex flex-col gap-5 flex-1 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-lg [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-sand-panel [&::-webkit-scrollbar-thumb]:bg-sand-thumb"
          >
            {messages.map((msg, index) => (
              <div
                key={`ja-${index}`}
                className="mx-auto w-full max-w-[29em] font-serif text-lg leading-[1.8] text-dim"
              >
                {msg.original}
              </div>
            ))}
            {interimMessage?.original && (
              <div className="mx-auto w-full max-w-[29em] rounded-md border-l-[3px] border-brand-line bg-brand-soft py-2.5 pr-3.5 pl-4 font-serif text-lg leading-[1.8] text-dim italic motion-safe:animate-pulse">
                {interimMessage.original}
                <span className="ml-1 inline-block h-4 w-1.5 rounded-xs bg-brand-deep align-middle" />
              </div>
            )}
          </div>
        </div>

        <div
          data-testid="translation-panel"
          className="order-1 md:order-none bg-sand-card border border-brand-line rounded-[14px] flex flex-col min-h-0 flex-[3] md:flex-none overflow-hidden"
        >
          <div className="px-[22px] py-3 bg-brand-soft border-b border-brand-line text-[10.5px] font-bold tracking-[0.14em] text-brand-deep uppercase shrink-0">
            {lang?.toUpperCase()} (Translation)
          </div>
          <div
            ref={translationScrollRef}
            data-testid="translation-scroll"
            className="px-5 sm:px-[26px] py-[22px] overflow-y-auto flex flex-col gap-5 flex-1 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-lg [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-sand-card [&::-webkit-scrollbar-thumb]:bg-sand-thumb"
          >
            {listenerState === 'waiting' && messages.length === 0 && (
              <div className="h-full flex items-center justify-center">
                <p className="text-center font-serif text-base font-medium text-dim">
                  Waiting for operator to start the feed…
                </p>
              </div>
            )}
            {messages.map((msg, index) => (
              <div
                key={`translation-${index}`}
                className="mx-auto w-full max-w-[34em] font-serif text-[19px] leading-[1.85] text-read"
              >
                {msg.translation}
              </div>
            ))}
            {interimMessage?.translation && (
              <div className="mx-auto w-full max-w-[34em] rounded-md border-l-[3px] border-brand-line bg-brand-soft py-2.5 pr-3.5 pl-4 font-serif text-[19px] leading-[1.85] text-read italic opacity-80 motion-safe:animate-pulse">
                {interimMessage.translation}
                <span className="ml-1 inline-block h-4 w-1.5 rounded-xs bg-brand-deep align-middle" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
