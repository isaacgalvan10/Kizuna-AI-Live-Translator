import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { isAxiosError } from 'axios';
import { QRCodeCanvas } from 'qrcode.react';
import api from '../api';
import { useAudioInput } from '../audio/useAudioInput';
import { FEED_BUTTON_RAMPS, OPERATOR_STATE_VISUALS } from '../feedStateVisuals';
import type { FeedState } from '../feedStateVisuals';
import { FOCUS } from '../focus';
import { WS_ORIGIN } from '../ws';
import AudioInputPanel from './AudioInputPanel';
import BrandMark from './BrandMark';
import ErrorBanner from './ErrorBanner';

const TOKEN_STORAGE_KEY = 'kizuna_operator_token';
// The QR must encode the address guests can actually reach. In production that
// is the app's own origin; VITE_PUBLIC_ORIGIN overrides it for setups where the
// operator's URL (e.g. localhost) differs from the guests' URL.
const PUBLIC_ORIGIN = import.meta.env.VITE_PUBLIC_ORIGIN || window.location.origin;

function guestJoinUrl(qrHash: string) {
  return `${PUBLIC_ORIGIN}/?qr=${encodeURIComponent(qrHash)}`;
}

function qrFileName(churchName: string) {
  const slug = churchName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `kizuna-${slug || 'church'}-qr.png`;
}

interface RoomSummary {
  id: number;
  is_live: boolean;
}

interface OperatorChurch {
  id: number;
  name: string;
  qr_code_hash: string;
  rooms: RoomSummary[];
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

// Shared feed-button chrome; the per-state state-colour ramps (state outranks
// the brand) come from FEED_BUTTON_RAMPS in feedStateVisuals.ts.
const FEED_BUTTON =
  'cursor-pointer rounded-2xl bg-linear-to-b py-5 text-[21px] font-extrabold tracking-[0.02em] text-btn-ink transition-[filter] duration-150 enabled:hover:brightness-[1.08] enabled:active:brightness-[0.94] disabled:cursor-not-allowed disabled:bg-none disabled:bg-sand-deep disabled:text-mute';

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
  const qrCanvasRef = useRef<HTMLCanvasElement>(null);
  const isSendingAudio = useRef(false);

  const roomId = church?.rooms[0]?.id ?? null;
  const audioInput = useAudioInput(Boolean(token) && church !== null && roomId !== null);
  const { beginCapture, endCapture } = audioInput;

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setChurch(null);
    setStatus('stopped');
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
    endCapture();
    disconnectSockets();
    setError(null);
  }, [clearSession, endCapture, disconnectSockets]);

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

  // Tear down the sockets if the console is unmounted; the audio hook owns its
  // own stream and context and releases them on unmount through `enabled`.
  useEffect(
    () => () => {
      disconnectSockets();
    },
    [disconnectSockets]
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
        await beginCapture((pcm16) => {
          if (!isSendingAudio.current) return;
          if (socket.readyState !== WebSocket.OPEN) return;
          socket.send(pcm16.buffer);
        });

        isSendingAudio.current = true;
        await controlFeed('start');
      } catch {
        // The audio panel owns the specific message (permission, device, rate).
        isSendingAudio.current = false;
        endCapture();
        if (streamWs.current === socket) {
          streamWs.current = null;
          socket.close();
        }
      }
    };

    socket.onclose = () => {
      isSendingAudio.current = false;
      endCapture();
      if (streamWs.current === socket) {
        streamWs.current = null;
        setError(
          opened
            ? 'The audio stream dropped. Press Stop, then Start, to reconnect.'
            : 'Could not open the audio stream. Check the connection, then press Start again.'
        );
      }
    };
  }, [token, roomId, beginCapture, endCapture, controlFeed]);

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
    isSendingAudio.current = false;
    endCapture();
    const socket = streamWs.current;
    streamWs.current = null;
    socket?.close();
  };

  const handleDownloadQr = () => {
    const canvas = qrCanvasRef.current;
    if (!canvas || !church) return;
    const link = document.createElement('a');
    link.href = canvas.toDataURL('image/png');
    link.download = qrFileName(church.name);
    link.click();
  };

  if (!token || !church) {
    return (
      <div className="flex items-center justify-center min-h-screen p-5">
        <form
          onSubmit={handleLogin}
          className="w-full max-w-md rounded-3xl border border-line bg-sand-card px-8 py-10 sm:px-10 sm:py-11"
          aria-label="Operator login"
        >
          <div className="text-center mb-8.5">
            <BrandMark size="page" />
            <p className="mt-3 text-[11px] font-bold uppercase tracking-[0.18em] text-dim">
              Operator Console
            </p>
          </div>

          <div className="space-y-5">
            <div>
              <label
                htmlFor="operator-email"
                className="block mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-dim"
              >
                Email
              </label>
              <input
                id="operator-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`w-full rounded-xl border border-line bg-sand-raise px-[15px] py-[13px] text-base font-medium text-ink ${FOCUS}`}
              />
            </div>

            <div>
              <label
                htmlFor="operator-password"
                className="block mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-dim"
              >
                Password
              </label>
              <input
                id="operator-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full rounded-xl border border-line bg-sand-raise px-[15px] py-[13px] text-base font-medium text-ink ${FOCUS}`}
              />
            </div>

            {error && <ErrorBanner message={error} />}

            <button
              type="submit"
              disabled={isBusy}
              className={`w-full mt-2 cursor-pointer rounded-2xl border border-btn-border bg-linear-to-b from-btn to-btn-deep py-4 text-[19px] font-extrabold tracking-[0.02em] text-btn-ink transition-[filter] duration-150 enabled:hover:brightness-[1.08] enabled:active:brightness-[0.94] disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
            >
              Log in
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 pt-14 pb-12">
      <div className="rounded-3xl border border-line bg-sand-card p-6 sm:p-9">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-7">
          <div>
            <h1 className="font-serif text-[27px] font-bold tracking-[-0.01em] text-ink">
              {church.name}
            </h1>
            <p className="mt-2.5 inline-block rounded-md border border-line bg-sand-deep px-2.5 py-[3px] font-mono text-[13px] text-dim">
              Room #{church.rooms[0]?.id}
            </p>
          </div>

          <div
            role="status"
            aria-live="polite"
            className={`flex items-center gap-2 rounded-full border px-[18px] py-[11px] text-[12.5px] font-bold tracking-[0.09em] uppercase shadow-float ${OPERATOR_STATE_VISUALS[status].pill}`}
          >
            <span className={`h-[11px] w-[11px] rounded-full ${OPERATOR_STATE_VISUALS[status].dot}`} />
            {OPERATOR_STATE_VISUALS[status].label}
          </div>
        </div>

        {roomId === null ? (
          <div className="rounded-2xl border border-line-soft bg-sand-panel p-8 text-center">
            <p className="text-base font-bold text-body">
              No room configured for this church. Ask your church admin to set one up.
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-line-soft bg-sand-panel p-6.5 space-y-4.5">
            {error && <ErrorBanner message={error} />}

            <AudioInputPanel audio={audioInput} />

            <div className="border-t border-line-soft" />

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
              <button
                onClick={handleStart}
                disabled={status === 'live'}
                className={`${FEED_BUTTON} ${FEED_BUTTON_RAMPS.live.from} ${FEED_BUTTON_RAMPS.live.to} ${FOCUS}`}
              >
                <span aria-hidden="true" className="mr-[11px] align-[2px] text-[0.68em] opacity-90">
                  ▶
                </span>
                {status === 'paused' ? 'Resume' : 'Start'}
              </button>
              <button
                onClick={handlePause}
                disabled={status !== 'live'}
                className={`${FEED_BUTTON} ${FEED_BUTTON_RAMPS.paused.from} ${FEED_BUTTON_RAMPS.paused.to} ${FOCUS}`}
              >
                Pause
              </button>
              <button
                onClick={handleStop}
                disabled={status === 'stopped'}
                className={`${FEED_BUTTON} ${FEED_BUTTON_RAMPS.danger.from} ${FEED_BUTTON_RAMPS.danger.to} ${FOCUS}`}
              >
                Stop
              </button>
            </div>

            <p className="text-center text-[13px] text-dim">
              {status === 'live' &&
                `Streaming the ${audioInput.settings.mode === 'mixer' ? 'mixer' : 'microphone'} feed. Translations are live.`}
              {status === 'paused' && 'Feed paused. Guests see the Paused banner.'}
              {status === 'stopped' && 'Press Start when the sermon begins.'}
            </p>
          </div>
        )}

        <div className="mt-5.5 flex flex-col sm:flex-row items-center gap-6 rounded-2xl border border-line bg-sand-panel p-6">
          <div className="shrink-0 rounded-xl bg-white p-3 shadow-qr">
            <QRCodeCanvas
              ref={qrCanvasRef}
              value={guestJoinUrl(church.qr_code_hash)}
              size={512}
              level="M"
              marginSize={4}
              style={{ width: 176, height: 176 }}
              aria-label="Guest QR code"
            />
          </div>
          <div className="min-w-0 space-y-2.5 text-center sm:text-left">
            <h2 className="font-serif text-[19px] font-bold text-ink">Guest QR</h2>
            <p className="text-[13px] leading-[1.55] text-dim">
              Print this code and place it where guests can scan it. It is permanent for
              this church — the same QR keeps working when the operator password changes.
            </p>
            <p className="font-mono text-xs text-dim break-all">
              {guestJoinUrl(church.qr_code_hash)}
            </p>
            <button
              onClick={handleDownloadQr}
              className={`cursor-pointer rounded-xl border border-ink bg-ink px-4.5 py-2.5 text-[13px] font-bold text-sand-raise transition-[filter] duration-150 hover:brightness-[1.15] ${FOCUS}`}
            >
              Download QR
            </button>
          </div>
        </div>

        <div className="mt-6.5 flex justify-end">
          <button
            onClick={handleLogout}
            className={`cursor-pointer rounded-xl px-4 py-2.5 text-[13px] font-bold text-dim transition-colors duration-150 hover:bg-danger-soft hover:text-danger-ink ${FOCUS}`}
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}
