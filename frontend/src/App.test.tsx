import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import App from './App';
import api from './api';

vi.mock('./api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));

const mockedPost = api.post as unknown as Mock;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
    this.readyState = FakeWebSocket.OPEN;
  }

  send() {}

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
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

class FakeUtterance {
  text: string;
  lang = '';
  voice: unknown = null;
  volume = 1;

  constructor(text: string) {
    this.text = text;
  }
}

const speechSynthesis = {
  speak: vi.fn(),
  cancel: vi.fn(),
  getVoices: vi.fn(() => [] as { lang: string; name: string }[]),
};

const PRE_SERVICE_JOIN = {
  status: 'success',
  user_id: 11,
  church_name: 'Kizuna Test Church',
  is_live: false,
  room_id: 3,
};

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

beforeEach(() => {
  FakeWebSocket.reset();
  vi.clearAllMocks();
  vi.stubGlobal('WebSocket', FakeWebSocket);
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance);
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: speechSynthesis,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the whole Sunday flow, through the app router', () => {
  it('takes a guest from the scanned QR code to a live, audible feed and through pause to the end', async () => {
    const user = userEvent.setup();
    mockedPost.mockResolvedValue({ data: PRE_SERVICE_JOIN });

    // 1. Scan the QR before the service starts.
    renderApp('/?qr=test-hash-123');

    expect(await screen.findByText('Kizuna Test Church')).toBeInTheDocument();
    expect(screen.getByText(/hasn't started/i)).toBeInTheDocument();
    expect(mockedPost).toHaveBeenCalledWith('/api/join/test-hash-123');

    // 2. Pick a language; the router lands on the listener view, waiting.
    await user.click(screen.getByRole('button', { name: /english/i }));

    expect(screen.getByText('Live Translation')).toBeInTheDocument();
    expect(screen.getByText(/waiting for operator to start the feed/i)).toBeInTheDocument();
    const socket = FakeWebSocket.find('/ws/listen/3/en');

    // 3. The operator starts: the guest goes live without re-scanning.
    act(() => socket.receive({ type: 'feed_state', data: 'live' }));

    expect(screen.getByRole('status')).toHaveTextContent('Live');
    expect(screen.queryByText(/waiting for operator/i)).not.toBeInTheDocument();

    // 4. Enabling Audio primes the voice engine.
    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    expect(screen.getByRole('button', { name: /audio: on/i })).toBeInTheDocument();
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(1);
    expect(speechSynthesis.speak.mock.calls[0][0].text).toMatch(/audio active/i);

    // 5. A translation arrives and is both shown and spoken.
    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '神は愛です。', translation: 'God is love.' },
      })
    );

    expect(
      within(screen.getByTestId('translation-panel')).getByText('God is love.')
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId('japanese-panel')).getByText('神は愛です。')
    ).toBeInTheDocument();
    expect(speechSynthesis.speak.mock.calls[1][0].text).toBe('God is love.');

    // 6. Pause for worship: banner up, speech cancelled.
    speechSynthesis.cancel.mockClear();
    act(() => socket.receive({ type: 'feed_state', data: 'paused' }));

    expect(screen.getByText(/paused — worship music/i)).toBeInTheDocument();
    expect(speechSynthesis.cancel).toHaveBeenCalled();

    // 7. Resume: the banner clears and translations flow again.
    act(() => socket.receive({ type: 'feed_state', data: 'live' }));

    expect(screen.queryByText(/paused — worship music/i)).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Live');

    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '主を賛美します。', translation: 'We praise the Lord.' },
      })
    );

    expect(
      within(screen.getByTestId('translation-panel')).getByText('We praise the Lord.')
    ).toBeInTheDocument();
    expect(speechSynthesis.speak.mock.calls[2][0].text).toBe('We praise the Lord.');

    // 8. Stop after the service: ended, audio taken away.
    act(() => socket.receive({ type: 'feed_state', data: 'stopped' }));

    expect(screen.getByText(/service ended/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeDisabled();
  });
});
