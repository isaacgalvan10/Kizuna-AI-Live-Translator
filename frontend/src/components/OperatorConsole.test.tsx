import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import OperatorConsole from './OperatorConsole';
import { AUDIO_INPUT_STORAGE_KEY } from '../audio/audioInput';
import { OPERATOR_STATE_VISUALS } from '../feedStateVisuals';
import api from '../api';
import { retiredStyleViolations } from '../test/retiredStyles';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const mockedGet = api.get as unknown as Mock;
const mockedPost = api.post as unknown as Mock;

const TOKEN_KEY = 'kizuna_operator_token';
const CHURCH = {
  id: 7,
  name: 'Kizuna Test Church',
  qr_code_hash: 'test-qr-hash',
  rooms: [{ id: 3, is_live: false }],
};

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: unknown) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  static find(urlPart: string): FakeWebSocket {
    const match = FakeWebSocket.instances.find((socket) => socket.url.includes(urlPart));
    if (!match) {
      throw new Error(`No FakeWebSocket connected to ${urlPart}`);
    }
    return match;
  }

  static reset() {
    FakeWebSocket.instances = [];
  }
}

function fakeStream() {
  const track = { stop: vi.fn(), onended: null as null | (() => void) };
  return {
    track,
    stream: {
      getTracks: () => [track],
      getAudioTracks: () => [track],
    } as unknown as MediaStream,
  };
}

const DEFAULT_INPUT_DEVICES = [
  { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
  { deviceId: 'usb-mixer', kind: 'audioinput', label: 'USB Mixer' },
  { deviceId: 'speakers', kind: 'audiooutput', label: 'Speakers' },
];

interface AudioCaptureOptions {
  sampleRate?: number;
  devices?: typeof DEFAULT_INPUT_DEVICES;
  getUserMedia?: Mock;
  waveform?: (data: Float32Array) => void;
  contextState?: AudioContextState;
  resume?: Mock;
}

function stubAudioCapture(options: AudioCaptureOptions = {}) {
  const processor = {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onaudioprocess: null as null | ((event: AudioProcessingEvent) => void),
  };
  const analyser = {
    fftSize: 2048,
    connect: vi.fn(),
    disconnect: vi.fn(),
    getFloatTimeDomainData: vi.fn((data: Float32Array) => {
      if (options.waveform) options.waveform(data);
      else data.fill(0);
    }),
  };
  const source = { connect: vi.fn(), disconnect: vi.fn() };
  const context = {
    sampleRate: options.sampleRate ?? 16000,
    state: (options.contextState ?? 'running') as AudioContextState,
    destination: {},
    resume:
      options.resume ??
      vi.fn(async () => {
        context.state = 'running';
      }),
    close: vi.fn().mockResolvedValue(undefined),
    createMediaStreamSource: vi.fn(() => source),
    createAnalyser: vi.fn(() => analyser),
    createScriptProcessor: vi.fn(() => processor),
  };
  const streams: ReturnType<typeof fakeStream>[] = [];
  const getUserMedia =
    options.getUserMedia ??
    vi.fn(async () => {
      const made = fakeStream();
      streams.push(made);
      return made.stream;
    });
  const enumerateDevices = vi.fn(async () => options.devices ?? DEFAULT_INPUT_DEVICES);
  const deviceChangeListeners = new Set<() => void>();
  const mediaDevices = {
    getUserMedia,
    enumerateDevices,
    addEventListener: vi.fn((type: string, listener: () => void) => {
      if (type === 'devicechange') deviceChangeListeners.add(listener);
    }),
    removeEventListener: vi.fn((type: string, listener: () => void) => {
      if (type === 'devicechange') deviceChangeListeners.delete(listener);
    }),
  };
  Object.defineProperty(window.navigator, 'mediaDevices', {
    configurable: true,
    value: mediaDevices,
  });

  vi.stubGlobal(
    'AudioContext',
    vi.fn(function AudioContextStub() {
      return context;
    })
  );
  return {
    processor,
    context,
    analyser,
    source,
    getUserMedia,
    enumerateDevices,
    fireDeviceChange() {
      for (const listener of deviceChangeListeners) listener();
    },
    lastTrack: () => streams[streams.length - 1]?.track,
  };
}

async function renderConsoleWithStoredSession() {
  localStorage.setItem(TOKEN_KEY, 'stored-token');
  mockedGet.mockResolvedValue({ data: CHURCH });
  const view = render(<OperatorConsole />);
  await screen.findByText('Kizuna Test Church');
  await waitFor(() =>
    expect(
      FakeWebSocket.instances.some((socket) => socket.url.includes('/ws/listen/3/operator'))
    ).toBe(true)
  );
  return view;
}

// The redesign's guard rails, not its look: jsdom has no CSS engine, so the
// restyle is pinned by what must be absent via the shared guard in
// test/retiredStyles.ts. The QR card's bare `bg-white` is deliberate — a
// scanner/print quiet zone — so it is the one explicit allowance.
const QR_QUIET_ZONE_ALLOWANCE = ['bg-white'];

const originalGetContext = HTMLCanvasElement.prototype.getContext;

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  FakeWebSocket.reset();
  vi.stubGlobal('WebSocket', FakeWebSocket);
  stubAudioCapture();
  // jsdom has no 2D canvas; qrcode.react bails out cleanly when getContext is
  // null, but jsdom's "not implemented" notice floods the test log without this.
  HTMLCanvasElement.prototype.getContext =
    (() => null) as typeof HTMLCanvasElement.prototype.getContext;
});

afterEach(() => {
  cleanup();
  HTMLCanvasElement.prototype.getContext = originalGetContext;
  vi.unstubAllGlobals();
});

describe('when logged out', () => {
  it('shows the login form and does not call the API', () => {
    render(<OperatorConsole />);

    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument();
    expect(mockedGet).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('does not reveal the console controls', () => {
    render(<OperatorConsole />);

    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
    expect(screen.queryByText('Kizuna Test Church')).not.toBeInTheDocument();
  });
});

describe('login', () => {
  it('stores the token and shows the console after a successful login', async () => {
    const user = userEvent.setup();
    mockedPost.mockResolvedValueOnce({
      data: { access_token: 'fresh-token', token_type: 'bearer', church_id: 7 },
    });
    mockedGet.mockResolvedValue({ data: CHURCH });

    render(<OperatorConsole />);
    await user.type(screen.getByLabelText('Email'), 'operator@kizuna.test');
    await user.type(screen.getByLabelText('Password'), 'kizuna-operator-test');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByText('Kizuna Test Church')).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBe('fresh-token');
    expect(mockedPost).toHaveBeenCalledWith('/api/operator/login', {
      email: 'operator@kizuna.test',
      password: 'kizuna-operator-test',
    });
    expect(mockedGet).toHaveBeenCalledWith('/api/operator/church', {
      headers: { Authorization: 'Bearer fresh-token' },
    });
  });

  it('keeps the operator on the form when credentials are rejected', async () => {
    const user = userEvent.setup();
    mockedPost.mockRejectedValueOnce(new Error('Request failed with status code 401'));

    render(<OperatorConsole />);
    await user.type(screen.getByLabelText('Email'), 'operator@kizuna.test');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid email or password/i);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
  });

  it('distinguishes an unreachable server from bad credentials', async () => {
    const user = userEvent.setup();
    mockedPost.mockRejectedValueOnce(
      Object.assign(new Error('Network Error'), { isAxiosError: true, response: undefined })
    );

    render(<OperatorConsole />);
    await user.type(screen.getByLabelText('Email'), 'operator@kizuna.test');
    await user.type(screen.getByLabelText('Password'), 'kizuna-operator-test');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the server/i);
  });
});

describe('a stored session', () => {
  it('restores the console from the stored token', async () => {
    await renderConsoleWithStoredSession();

    expect(screen.getByText('Room #3')).toBeInTheDocument();
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
    expect(mockedGet).toHaveBeenCalledWith('/api/operator/church', {
      headers: { Authorization: 'Bearer stored-token' },
    });
  });

  it('falls back to the login form when the stored token is rejected', async () => {
    localStorage.setItem(TOKEN_KEY, 'expired-token');
    mockedGet.mockRejectedValue(new Error('Request failed with status code 401'));

    render(<OperatorConsole />);

    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('tells the operator when the church has no room', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored-token');
    mockedGet.mockResolvedValue({ data: { ...CHURCH, rooms: [] } });

    render(<OperatorConsole />);

    expect(await screen.findByText(/no room configured/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
  });
});

describe('feed control', () => {
  it('offers only the valid actions for the current status', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();

    const start = screen.getByRole('button', { name: 'Start' });
    expect(start).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeDisabled();

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(start);
    act(() => FakeWebSocket.find('/ws/stream/').open());

    expect(await screen.findByRole('status')).toHaveTextContent('Live');
    expect(screen.getByRole('button', { name: 'Start' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled();

    mockedPost.mockResolvedValueOnce({ data: { status: 'paused' } });
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Paused');
    expect(screen.getByRole('button', { name: 'Resume' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled();
  });

  it('opens the authenticated audio stream and starts the feed', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });

    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith('/api/operator/rooms/3/start', null, {
        headers: { Authorization: 'Bearer stored-token' },
      })
    );
    const streamSocket = FakeWebSocket.find('/ws/stream/');
    expect(streamSocket.url).toBe('ws://localhost:5173/ws/stream/3?token=stored-token');
    expect(await screen.findByRole('status')).toHaveTextContent('Live');
  });

  it('pauses the feed through the API', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await screen.findByRole('status');
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Live')
    );

    mockedPost.mockResolvedValueOnce({ data: { status: 'paused' } });
    await user.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith('/api/operator/rooms/3/pause', null, {
        headers: { Authorization: 'Bearer stored-token' },
      })
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Paused');
  });

  it('stops the feed through the API and closes the audio stream', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));

    mockedPost.mockResolvedValueOnce({ data: { status: 'stopped' } });
    await user.click(screen.getByRole('button', { name: 'Stop' }));

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith('/api/operator/rooms/3/stop', null, {
        headers: { Authorization: 'Bearer stored-token' },
      })
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Stopped');
    expect(FakeWebSocket.find('/ws/stream/').readyState).toBe(FakeWebSocket.CLOSED);
  });

  it('reports a failed audio-stream handshake and keeps Start available', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();

    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').close());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not open the audio stream/i
    );
    expect(mockedPost).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Start' })).toBeEnabled();
    expect(screen.getByRole('status')).toHaveTextContent('Stopped');
  });

  it('tells the operator to stop before reconnecting a dropped stream', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));

    act(() => FakeWebSocket.find('/ws/stream/').close());

    expect(await screen.findByRole('alert')).toHaveTextContent(/press stop, then start/i);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeEnabled();
  });

  it('resumes with the start endpoint when paused', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));

    mockedPost.mockResolvedValueOnce({ data: { status: 'paused' } });
    await user.click(screen.getByRole('button', { name: 'Pause' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Paused'));

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Resume' }));

    await waitFor(() =>
      expect(mockedPost).toHaveBeenCalledWith('/api/operator/rooms/3/start', null, {
        headers: { Authorization: 'Bearer stored-token' },
      })
    );
    expect(await screen.findByRole('status')).toHaveTextContent('Live');
  });
});

describe('audio input', () => {
  const AUDIO_INPUT_KEY = AUDIO_INPUT_STORAGE_KEY;

  it('lists audio input devices after microphone permission is granted', async () => {
    await renderConsoleWithStoredSession();

    const select = await screen.findByLabelText('Input device');
    await waitFor(() =>
      expect(within(select).getByRole('option', { name: 'USB Mixer' })).toBeInTheDocument()
    );

    expect(
      within(select).getByRole('option', { name: 'Default Microphone' })
    ).toBeInTheDocument();
    expect(
      within(select).getByRole('option', { name: 'System default input' })
    ).toBeInTheDocument();
    expect(within(select).queryByRole('option', { name: 'Speakers' })).not.toBeInTheDocument();
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
  });

  it('persists the selected input device and uses it for capture', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    const select = await screen.findByLabelText('Input device');
    await waitFor(() =>
      expect(within(select).getByRole('option', { name: 'USB Mixer' })).toBeInTheDocument()
    );

    await user.selectOptions(select, 'usb-mixer');

    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem(AUDIO_INPUT_KEY) ?? 'null')).toEqual({
        deviceId: 'usb-mixer',
        mode: 'mixer',
      })
    );
    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenLastCalledWith({
        audio: expect.objectContaining({ deviceId: { exact: 'usb-mixer' } }),
      })
    );

    cleanup();
    render(<OperatorConsole />);

    const restored = await screen.findByLabelText('Input device');
    await waitFor(() =>
      expect(within(restored).getByRole('option', { name: 'USB Mixer' })).toBeInTheDocument()
    );
    expect(restored).toHaveValue('usb-mixer');
    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenLastCalledWith({
        audio: expect.objectContaining({ deviceId: { exact: 'usb-mixer' } }),
      })
    );
  });

  it('keeps browser speech processing on only for the laptop microphone', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    await screen.findByLabelText('Input device');

    expect(screen.getByRole('radio', { name: /mixer \/ line input/i })).toBeChecked();
    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenLastCalledWith({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
    );

    await user.click(screen.getByRole('radio', { name: /laptop microphone/i }));

    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenLastCalledWith({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    );
    expect(JSON.parse(localStorage.getItem(AUDIO_INPUT_KEY) ?? 'null')).toEqual({
      deviceId: null,
      mode: 'microphone',
    });

    await user.click(screen.getByRole('radio', { name: /mixer \/ line input/i }));

    await waitFor(() =>
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenLastCalledWith({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
    );
    expect(JSON.parse(localStorage.getItem(AUDIO_INPUT_KEY) ?? 'null')).toEqual({
      deviceId: null,
      mode: 'mixer',
    });
  });

  it('shows arriving audio on the level meter before Start', async () => {
    stubAudioCapture({
      waveform: (data) => {
        for (let i = 0; i < data.length; i++) data[i] = 0.5 * Math.sin(i / 8);
      },
    });
    await renderConsoleWithStoredSession();

    const meter = await screen.findByRole('meter', { name: 'Input level' });

    await waitFor(() =>
      expect(Number(meter.getAttribute('aria-valuenow'))).toBeGreaterThan(50)
    );
    expect(screen.getByText('Audio detected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start' })).toBeEnabled();
  });

  it('shows an empty meter when the input is silent', async () => {
    await renderConsoleWithStoredSession();

    const meter = await screen.findByRole('meter', { name: 'Input level' });

    expect(meter).toHaveAttribute('aria-valuenow', '0');
    expect(screen.getByText('No audio')).toBeInTheDocument();
  });

  it('falls back to the default input when the selected device is unplugged', async () => {
    localStorage.setItem(
      AUDIO_INPUT_KEY,
      JSON.stringify({ deviceId: 'usb-mixer', mode: 'microphone' })
    );
    const capture = stubAudioCapture();
    await renderConsoleWithStoredSession();
    const select = await screen.findByLabelText('Input device');
    await waitFor(() => expect(select).toHaveValue('usb-mixer'));

    capture.enumerateDevices.mockResolvedValue([
      { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
    ]);
    act(() => capture.fireDeviceChange());

    expect(await screen.findByRole('alert')).toHaveTextContent(/input device disconnected/i);
    await waitFor(() => expect(select).toHaveValue(''));
    // The fallback is for this visit only: a reload tries the saved device again.
    expect(JSON.parse(localStorage.getItem(AUDIO_INPUT_KEY) ?? 'null')).toEqual({
      deviceId: 'usb-mixer',
      mode: 'microphone',
    });
    await waitFor(() => {
      const calls = (navigator.mediaDevices.getUserMedia as unknown as Mock).mock.calls;
      expect(calls.at(-1)?.[0].audio).not.toHaveProperty('deviceId');
    });
  });

  it('explains denied permission and lets the operator retry', async () => {
    const user = userEvent.setup();
    const userMedia = stubAudioCapture();
    const denied = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' });
    (userMedia.getUserMedia as Mock)
      .mockRejectedValueOnce(denied)
      .mockResolvedValueOnce(fakeStream().stream);
    await renderConsoleWithStoredSession();

    expect(await screen.findByRole('alert')).toHaveTextContent(/allow microphone access/i);

    await user.click(screen.getByRole('button', { name: 'Retry audio input' }));

    await waitFor(() => expect(userMedia.getUserMedia).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('resamples a browser capture that ignores the 16 kHz request', async () => {
    const user = userEvent.setup();
    const capture = stubAudioCapture({ sampleRate: 48000 });
    await renderConsoleWithStoredSession();

    expect(
      await screen.findByText(/48 kHz.*resampling to 16 kHz/i)
    ).toBeInTheDocument();

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));

    act(() => {
      capture.processor.onaudioprocess?.({
        inputBuffer: { getChannelData: () => new Float32Array(4096).fill(0.5) },
      } as unknown as AudioProcessingEvent);
    });

    const sent = FakeWebSocket.find('/ws/stream/').sent;
    expect(sent).toHaveLength(1);
    const bytes = sent[0] as ArrayBuffer;
    expect(bytes.byteLength).toBeGreaterThan(2000);
    expect(bytes.byteLength).toBeLessThan(4000);
  });

  it('resumes a suspended audio context when Start is pressed', async () => {
    const user = userEvent.setup();
    const resume = vi.fn();
    const capture = stubAudioCapture({ contextState: 'suspended', resume });
    resume
      .mockResolvedValueOnce(undefined)
      .mockImplementation(async () => {
        capture.context.state = 'running';
      });
    await renderConsoleWithStoredSession();

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());

    await waitFor(() => expect(resume).toHaveBeenCalledTimes(2));
    expect(capture.processor.connect).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));
  });

  it('keeps streaming through an unplug by switching to the default input', async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      AUDIO_INPUT_KEY,
      JSON.stringify({ deviceId: 'usb-mixer', mode: 'mixer' })
    );
    const capture = stubAudioCapture();
    await renderConsoleWithStoredSession();
    const select = await screen.findByLabelText('Input device');
    await waitFor(() => expect(select).toHaveValue('usb-mixer'));

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));

    act(() => {
      capture.processor.onaudioprocess?.({
        inputBuffer: { getChannelData: () => new Float32Array(4096).fill(0.5) },
      } as unknown as AudioProcessingEvent);
    });
    expect(FakeWebSocket.find('/ws/stream/').sent).toHaveLength(1);

    capture.enumerateDevices.mockResolvedValue([
      { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
    ]);
    act(() => capture.fireDeviceChange());

    await waitFor(() => expect(select).toHaveValue(''));
    await waitFor(() => expect(capture.getUserMedia).toHaveBeenCalledTimes(2));

    act(() => {
      capture.processor.onaudioprocess?.({
        inputBuffer: { getChannelData: () => new Float32Array(4096).fill(0.5) },
      } as unknown as AudioProcessingEvent);
    });
    expect(FakeWebSocket.find('/ws/stream/').sent).toHaveLength(2);
  });

  it('reacquires before capturing when the fallback input failed', async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      AUDIO_INPUT_KEY,
      JSON.stringify({ deviceId: 'usb-mixer', mode: 'microphone' })
    );
    const capture = stubAudioCapture();
    await renderConsoleWithStoredSession();
    const select = await screen.findByLabelText('Input device');
    await waitFor(() => expect(select).toHaveValue('usb-mixer'));

    (capture.getUserMedia as Mock).mockRejectedValueOnce(
      Object.assign(new Error('No input'), { name: 'NotFoundError' })
    );
    capture.enumerateDevices.mockResolvedValue([
      { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
    ]);
    act(() => capture.lastTrack()?.onended?.());

    expect(await screen.findByText(/could not open/i)).toBeInTheDocument();

    mockedPost.mockResolvedValueOnce({ data: { status: 'live' } });
    await user.click(screen.getByRole('button', { name: 'Start' }));
    act(() => FakeWebSocket.find('/ws/stream/').open());

    await waitFor(() => expect(capture.getUserMedia).toHaveBeenCalledTimes(3));
    expect(capture.processor.connect).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Live'));
  });
});

describe('feed state over WebSocket', () => {
  it('reflects feed_state events from the room', async () => {
    await renderConsoleWithStoredSession();
    const feedSocket = FakeWebSocket.find('/ws/listen/3/operator');
    expect(feedSocket.url).toBe('ws://localhost:5173/ws/listen/3/operator');
    expect(screen.getByRole('status')).toHaveTextContent('Stopped');

    act(() => feedSocket.receive({ type: 'feed_state', data: 'paused' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Paused');

    act(() => feedSocket.receive({ type: 'feed_state', data: 'live' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Live');

    act(() => feedSocket.receive({ type: 'feed_state', data: 'stopped' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Stopped');
  });

  it('starts the badge from the room is_live flag', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored-token');
    mockedGet.mockResolvedValue({ data: { ...CHURCH, rooms: [{ id: 3, is_live: true }] } });

    render(<OperatorConsole />);

    expect(await screen.findByRole('status')).toHaveTextContent('Live');
  });
});

describe('guest QR code', () => {
  it('shows the permanent join link for this church', async () => {
    await renderConsoleWithStoredSession();

    expect(screen.getByText('Guest QR')).toBeInTheDocument();
    expect(
      screen.getByText(`${window.location.origin}/?qr=test-qr-hash`)
    ).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /guest qr code/i })).toBeInTheDocument();
  });

  it('downloads the QR as a PNG for printing', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    const toDataURL = vi
      .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
      .mockReturnValue('data:image/png;base64,qr-bytes');
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});

    await user.click(screen.getByRole('button', { name: /download/i }));

    expect(toDataURL).toHaveBeenCalledWith('image/png');
    expect(click).toHaveBeenCalledTimes(1);

    toDataURL.mockRestore();
    click.mockRestore();
  });
});

describe('the Kizuna restyle', () => {
  it('presents the feed state pill through the shared module', async () => {
    await renderConsoleWithStoredSession();
    const feedSocket = FakeWebSocket.find('/ws/listen/3/operator');

    for (const state of ['live', 'paused', 'stopped'] as const) {
      act(() => feedSocket.receive({ type: 'feed_state', data: state }));

      const pill = screen.getByRole('status');
      expect(pill).toHaveClass(...OPERATOR_STATE_VISUALS[state].pill.split(' '));

      const dot = pill.querySelector('span');
      expect(dot).not.toBeNull();
      expect(dot).toHaveClass(...OPERATOR_STATE_VISUALS[state].dot.split(' '));
    }
  });
  it('keeps the feed buttons on the state button ramp, never the brand ramp', async () => {
    await renderConsoleWithStoredSession();
    const feedSocket = FakeWebSocket.find('/ws/listen/3/operator');

    const start = screen.getByRole('button', { name: 'Start' });
    expect(start).toHaveClass('from-live-btn', 'to-live-btn-deep', 'text-btn-ink');
    expect(start).not.toHaveClass('from-btn', 'to-btn-deep');

    expect(screen.getByRole('button', { name: 'Pause' })).toHaveClass(
      'from-paused-btn',
      'to-paused-btn-deep'
    );
    expect(screen.getByRole('button', { name: 'Stop' })).toHaveClass(
      'from-danger-btn',
      'to-danger-btn-deep'
    );

    // Resume is the same feed action as Start and keeps its emerald ramp.
    act(() => feedSocket.receive({ type: 'feed_state', data: 'paused' }));
    expect(screen.getByRole('button', { name: 'Resume' })).toHaveClass(
      'from-live-btn',
      'to-live-btn-deep'
    );
  });
  it('keeps the guest QR on a white card with its heavier warm shadow', async () => {
    await renderConsoleWithStoredSession();

    const qrWhite = screen.getByRole('img', { name: /guest qr code/i }).closest('div');
    expect(qrWhite).not.toBeNull();
    expect(qrWhite).toHaveClass('bg-white', 'shadow-qr');
  });
  it('renders the console without glass or the retired palette', async () => {
    const { container } = await renderConsoleWithStoredSession();

    expect(retiredStyleViolations(container, QR_QUIET_ZONE_ALLOWANCE)).toEqual([]);
  });

  it('renders the login card without glass or the retired palette', () => {
    const { container } = render(<OperatorConsole />);

    expect(retiredStyleViolations(container)).toEqual([]);
  });
});

describe('logout', () => {
  it('clears the token and returns to the login form', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();

    await user.click(screen.getByRole('button', { name: 'Log out' }));

    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(screen.queryByText('Kizuna Test Church')).not.toBeInTheDocument();
  });

  it('disconnects the feed-state socket', async () => {
    const user = userEvent.setup();
    await renderConsoleWithStoredSession();
    const feedSocket = FakeWebSocket.find('/ws/listen/3/operator');

    await user.click(screen.getByRole('button', { name: 'Log out' }));

    expect(feedSocket.readyState).toBe(FakeWebSocket.CLOSED);
  });
});
