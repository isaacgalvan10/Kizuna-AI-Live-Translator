import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { isAxiosError } from 'axios';
import api from '../api';

const TOKEN_STORAGE_KEY = 'kizuna_operator_token';
const WS_ORIGIN = 'ws://localhost:8000';

type FeedState = 'live' | 'paused' | 'stopped';

interface RoomSummary {
  id: number;
  is_live: boolean;
}

interface OperatorChurch {
  id: number;
  name: string;
  rooms: RoomSummary[];
}

const FEED_STATE_UI: Record<FeedState, { label: string; pill: string; dot: string }> = {
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
    label: 'Stopped',
    pill: 'bg-slate-100 border-slate-300 text-slate-600',
    dot: 'bg-slate-400',
  },
};

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="text-sm font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3"
    >
      {message}
    </p>
  );
}

export default function OperatorConsole() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_STORAGE_KEY)
  );
  const [church, setChurch] = useState<OperatorChurch | null>(null);
  const [status, setStatus] = useState<FeedState>('stopped');
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const feedStateWs = useRef<WebSocket | null>(null);
  const streamWs = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const processor = useRef<ScriptProcessorNode | null>(null);
  const microphoneStream = useRef<MediaStream | null>(null);
  const isSendingAudio = useRef(false);

  const roomId = church?.rooms[0]?.id ?? null;

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setChurch(null);
    setStatus('stopped');
  }, []);

  const teardownAudio = useCallback(() => {
    isSendingAudio.current = false;
    processor.current?.disconnect();
    processor.current = null;
    audioContext.current?.close();
    audioContext.current = null;
    microphoneStream.current?.getTracks().forEach((track) => track.stop());
    microphoneStream.current = null;
  }, []);

  const disconnectSockets = useCallback(() => {
    const feed = feedStateWs.current;
    feedStateWs.current = null;
    feed?.close();
    const stream = streamWs.current;
    streamWs.current = null;
    stream?.close();
  }, []);

  const handleLogout = useCallback(() => {
    clearSession();
    teardownAudio();
    disconnectSockets();
    setError(null);
  }, [clearSession, teardownAudio, disconnectSockets]);

  // Restore the session: resolve the operator's church and rooms from the stored token.
  useEffect(() => {
    if (!token || church) return;
    let cancelled = false;

    api
      .get<OperatorChurch>('/api/operator/church', { headers: authHeaders(token) })
      .then((response) => {
        if (cancelled) return;
        setChurch(response.data);
        setStatus(response.data.rooms[0]?.is_live ? 'live' : 'stopped');
      })
      .catch(() => {
        if (cancelled) return;
        clearSession();
      });

    return () => {
      cancelled = true;
    };
  }, [token, church, clearSession]);

  // Subscribe to the room's feed lifecycle events while the console is open.
  useEffect(() => {
    if (roomId === null) return;

    const socket = new WebSocket(`${WS_ORIGIN}/ws/listen/${roomId}/operator`);
    feedStateWs.current = socket;

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const isFeedState =
          payload.type === 'feed_state' &&
          (payload.data === 'live' || payload.data === 'paused' || payload.data === 'stopped');
        if (!isFeedState) return;

        setStatus(payload.data);
        if (payload.data === 'live') {
          isSendingAudio.current = streamWs.current?.readyState === WebSocket.OPEN;
        } else {
          isSendingAudio.current = false;
        }
      } catch {
        // Ignore malformed frames from the socket.
      }
    };

    return () => {
      if (feedStateWs.current === socket) feedStateWs.current = null;
      socket.close();
    };
  }, [roomId]);

  // Tear everything down if the console is unmounted.
  useEffect(
    () => () => {
      teardownAudio();
      disconnectSockets();
    },
    [teardownAudio, disconnectSockets]
  );

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsBusy(true);
    try {
      const response = await api.post('/api/operator/login', { email, password });
      localStorage.setItem(TOKEN_STORAGE_KEY, response.data.access_token);
      setToken(response.data.access_token);
      setPassword('');
    } catch (err) {
      setError(
        isAxiosError(err) && !err.response
          ? 'Could not reach the server. Check your connection and try again.'
          : 'Invalid email or password.'
      );
    } finally {
      setIsBusy(false);
    }
  };

  const controlFeed = useCallback(
    async (action: 'start' | 'pause' | 'stop'): Promise<boolean> => {
      if (!token || roomId === null) return false;
      setError(null);
      try {
        const response = await api.post(`/api/operator/rooms/${roomId}/${action}`, null, {
          headers: authHeaders(token),
        });
        setStatus(response.data.status);
        return true;
      } catch (err) {
        if (isAxiosError(err) && err.response?.status === 401) {
          clearSession();
          setError('Session expired. Please log in again.');
        } else {
          setError('Could not update the feed. Check the connection and try again.');
        }
        return false;
      }
    },
    [token, roomId, clearSession]
  );

  const openAudioPipeline = useCallback(() => {
    if (!token || roomId === null) return;
    setError(null);

    const socket = new WebSocket(
      `${WS_ORIGIN}/ws/stream/${roomId}?token=${encodeURIComponent(token)}`
    );
    streamWs.current = socket;

    // Guards the onclose copy: a socket that never opened failed the handshake
    // (Start is still available); a socket that opened was dropped mid-broadcast
    // (the operator must Stop before Start can rebuild the pipeline).
    let opened = false;

    socket.onopen = async () => {
      opened = true;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        microphoneStream.current = stream;

        const AudioContextCtor =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const context = new AudioContextCtor({ sampleRate: 16000 });
        audioContext.current = context;

        const source = context.createMediaStreamSource(stream);
        const node = context.createScriptProcessor(4096, 1, 1);
        processor.current = node;

        node.onaudioprocess = (audioEvent: AudioProcessingEvent) => {
          if (!isSendingAudio.current) return;
          if (socket.readyState !== WebSocket.OPEN) return;

          const inputData = audioEvent.inputBuffer.getChannelData(0);
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcm16[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7fff;
          }
          socket.send(pcm16.buffer);
        };

        source.connect(node);
        node.connect(context.destination);

        isSendingAudio.current = true;
        await controlFeed('start');
      } catch {
        setError('Microphone access failed. Check the mixer connection and permissions.');
        teardownAudio();
        if (streamWs.current === socket) {
          streamWs.current = null;
          socket.close();
        }
      }
    };

    socket.onclose = () => {
      teardownAudio();
      if (streamWs.current === socket) {
        streamWs.current = null;
        setError(
          opened
            ? 'The audio stream dropped. Press Stop, then Start, to reconnect.'
            : 'Could not open the audio stream. Check the connection, then press Start again.'
        );
      }
    };
  }, [token, roomId, controlFeed, teardownAudio]);

  const handleStart = async () => {
    if (status === 'stopped') {
      openAudioPipeline();
      return;
    }
    // Resume: the audio pipeline is still warm from before the pause.
    const ok = await controlFeed('start');
    if (ok) {
      isSendingAudio.current = streamWs.current?.readyState === WebSocket.OPEN;
    }
  };

  const handlePause = async () => {
    const ok = await controlFeed('pause');
    if (ok) isSendingAudio.current = false;
  };

  const handleStop = async () => {
    const ok = await controlFeed('stop');
    if (!ok) return;
    teardownAudio();
    const socket = streamWs.current;
    streamWs.current = null;
    socket?.close();
  };

  if (!token || !church) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <form
          onSubmit={handleLogin}
          className="bg-white rounded-3xl shadow-2xl p-8 sm:p-12 w-full max-w-md border border-slate-100"
          aria-label="Operator login"
        >
          <div className="text-center mb-10">
            <h1 className="text-4xl font-black tracking-tight text-indigo-600 mb-2">絆 KIZUNA</h1>
            <p className="text-sm text-slate-500 font-bold uppercase tracking-widest">
              Operator Console
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <label
                htmlFor="operator-email"
                className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2"
              >
                Email
              </label>
              <input
                id="operator-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-4 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all font-medium text-slate-800 text-lg"
              />
            </div>

            <div>
              <label
                htmlFor="operator-password"
                className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2"
              >
                Password
              </label>
              <input
                id="operator-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-4 bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all font-medium text-slate-800 text-lg"
              />
            </div>

            {error && <ErrorBanner message={error} />}

            <button
              type="submit"
              disabled={isBusy}
              className="w-full py-5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:bg-slate-300 text-white font-black rounded-2xl transition-all shadow-lg shadow-indigo-200 text-xl tracking-wide"
            >
              Log in
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto pt-10 sm:pt-20 px-4">
      <div className="bg-white rounded-3xl shadow-xl p-6 sm:p-10 border border-slate-100">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">{church.name}</h1>
            <p className="text-sm text-slate-500 font-mono mt-2 bg-slate-100 inline-block px-3 py-1 rounded">
              Room #{church.rooms[0]?.id}
            </p>
          </div>

          <div
            role="status"
            aria-live="polite"
            className={`flex items-center gap-3 px-5 py-3 rounded-full border font-black tracking-wide uppercase text-sm ${FEED_STATE_UI[status].pill}`}
          >
            <span className={`h-3 w-3 rounded-full ${FEED_STATE_UI[status].dot}`} />
            {FEED_STATE_UI[status].label}
          </div>
        </div>

        {roomId === null ? (
          <div className="p-8 bg-slate-50 rounded-2xl border border-slate-200 text-center">
            <p className="text-base font-bold text-slate-600">
              No room configured for this church. Ask your church admin to set one up.
            </p>
          </div>
        ) : (
          <div className="p-6 sm:p-10 bg-slate-50 rounded-2xl border border-slate-200 space-y-6">
            {error && <ErrorBanner message={error} />}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <button
                onClick={handleStart}
                disabled={status === 'live'}
                className="py-6 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-black rounded-2xl transition-all shadow-lg shadow-emerald-200/50 text-2xl tracking-wide"
              >
                {status === 'paused' ? 'Resume' : 'Start'}
              </button>
              <button
                onClick={handlePause}
                disabled={status !== 'live'}
                className="py-6 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-black rounded-2xl transition-all shadow-lg shadow-amber-200/50 text-2xl tracking-wide"
              >
                Pause
              </button>
              <button
                onClick={handleStop}
                disabled={status === 'stopped'}
                className="py-6 bg-rose-600 hover:bg-rose-700 active:bg-rose-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-black rounded-2xl transition-all shadow-lg shadow-rose-200/50 text-2xl tracking-wide"
              >
                Stop
              </button>
            </div>

            <p className="text-sm text-slate-500 font-medium text-center">
              {status === 'live' && 'Streaming the mixer feed. Translations are live.'}
              {status === 'paused' && 'Feed paused. Guests see the Paused banner.'}
              {status === 'stopped' && 'Press Start when the sermon begins.'}
            </p>
          </div>
        )}

        <div className="mt-8 flex justify-end">
          <button
            onClick={handleLogout}
            className="px-6 py-3 text-sm font-bold text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors"
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}
