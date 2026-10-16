import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Listener from './Listener';

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

function renderListener(
  path = '/listen/3/en',
  state?: { isLive: boolean }
) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: path, state }]}>
      <Routes>
        <Route path="/listen/:roomId/:lang" element={<Listener />} />
      </Routes>
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

describe('a guest who scans before the operator starts', () => {
  it('waits on the listener view with audio unavailable until the feed goes live', () => {
    renderListener('/listen/3/en', { isLive: false });

    expect(
      screen.getByText(/waiting for operator to start the feed/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeDisabled();
    expect(FakeWebSocket.find('/ws/listen/3/en')).toBeDefined();
  });
});

describe('following the live feed', () => {
  it('shows each translation with its Japanese transcript in its own panel', () => {
    renderListener('/listen/3/en', { isLive: true });

    act(() => {
      FakeWebSocket.find('/ws/listen/3/en').receive({
        type: 'live_translation',
        data: { original: '神は愛です。', translation: 'God is love.' },
      });
    });

    expect(
      within(screen.getByTestId('translation-panel')).getByText('God is love.')
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId('japanese-panel')).getByText('神は愛です。')
    ).toBeInTheDocument();
  });

  it('treats an arriving translation as proof the feed is live', () => {
    renderListener('/listen/3/en');
    expect(screen.getByText(/waiting for operator/i)).toBeInTheDocument();

    act(() => {
      FakeWebSocket.find('/ws/listen/3/en').receive({
        type: 'live_translation',
        data: { original: '主を賛美します。', translation: 'We praise the Lord.' },
      });
    });

    expect(screen.queryByText(/waiting for operator/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeEnabled();
  });

  it('shows the feed as live once the operator starts it', () => {
    renderListener('/listen/3/en', { isLive: false });

    act(() => {
      FakeWebSocket.find('/ws/listen/3/en').receive({ type: 'feed_state', data: 'live' });
    });

    expect(screen.queryByText(/waiting for operator/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeEnabled();
  });

  it('backfills the history when a guest joins late', () => {
    renderListener('/listen/3/ko', { isLive: true });

    act(() => {
      FakeWebSocket.find('/ws/listen/3/ko').receive({
        type: 'history',
        data: [
          { original: 'おはようございます。', translation: '좋은 아침입니다.' },
          { original: '今日は良い日です。', translation: '오늘은 좋은 날입니다.' },
        ],
      });
    });

    const translationPanel = screen.getByTestId('translation-panel');
    expect(within(translationPanel).getByText('좋은 아침입니다.')).toBeInTheDocument();
    expect(within(translationPanel).getByText('오늘은 좋은 날입니다.')).toBeInTheDocument();
  });
});

describe('the operator pauses for worship', () => {
  it('shows the paused banner and clears it when the feed resumes', () => {
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');

    act(() => socket.receive({ type: 'feed_state', data: 'paused' }));

    expect(screen.getByRole('status')).toHaveTextContent('Paused');
    expect(screen.getByText(/paused — worship music/i)).toBeInTheDocument();

    act(() => socket.receive({ type: 'feed_state', data: 'live' }));

    expect(screen.queryByText(/paused — worship music/i)).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Live');
  });

  it('shows the service as ended and takes audio away after a stop', () => {
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');

    act(() => socket.receive({ type: 'feed_state', data: 'stopped' }));

    expect(screen.getByText(/service ended/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeDisabled();
  });

  it('stays ended when an in-flight line arrives after the stop', () => {
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');
    act(() => socket.receive({ type: 'feed_state', data: 'stopped' }));

    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '最後の言葉。', translation: 'One last word.' },
      })
    );

    expect(screen.getByText(/service ended/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeDisabled();
  });
});

describe('listening over headphones', () => {
  it('primes the voice when audio is turned on, then speaks each translation', async () => {
    const user = userEvent.setup();
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');

    await user.click(screen.getByRole('button', { name: /audio: off/i }));

    expect(screen.getByRole('button', { name: /audio: on/i })).toBeInTheDocument();
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(1);
    expect(speechSynthesis.speak.mock.calls[0][0].text).toMatch(/audio active/i);

    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '神は愛です。', translation: 'God is love.' },
      })
    );

    expect(speechSynthesis.speak).toHaveBeenCalledTimes(2);
    expect(speechSynthesis.speak.mock.calls[1][0].text).toBe('God is love.');
  });

  it('stops speaking when audio is turned off', async () => {
    const user = userEvent.setup();
    renderListener('/listen/3/en', { isLive: true });

    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    await user.click(screen.getByRole('button', { name: /audio: on/i }));

    expect(speechSynthesis.cancel).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /audio: off/i })).toBeInTheDocument();
  });

  it('cancels speech the moment the operator pauses', async () => {
    const user = userEvent.setup();
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');
    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    speechSynthesis.cancel.mockClear();

    act(() => socket.receive({ type: 'feed_state', data: 'paused' }));

    expect(speechSynthesis.cancel).toHaveBeenCalled();
  });

  it("speaks in the guest's language with a matching voice", async () => {
    const koreanVoice = { lang: 'ko-KR', name: 'Yuna Natural' };
    speechSynthesis.getVoices.mockReturnValue([
      { lang: 'en-US', name: 'Samantha' },
      koreanVoice,
    ]);
    const user = userEvent.setup();
    renderListener('/listen/3/ko', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/ko');

    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '神は愛です。', translation: '하나님은 사랑이십니다.' },
      })
    );

    const spoken = speechSynthesis.speak.mock.calls[1][0];
    expect(spoken.voice).toBe(koreanVoice);
    expect(spoken.lang).toBe('ko-KR');
  });

  it('switching language cancels the old voice queue and primes the new voice', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[{ pathname: '/listen/3/en', state: { isLive: true } }]}>
        <Link to="/listen/3/ko" state={{ isLive: true }}>
          switch language
        </Link>
        <Routes>
          <Route path="/listen/:roomId/:lang" element={<Listener />} />
        </Routes>
      </MemoryRouter>
    );
    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    act(() =>
      FakeWebSocket.find('/ws/listen/3/en').receive({
        type: 'live_translation',
        data: { original: '神は愛です。', translation: 'God is love.' },
      })
    );
    speechSynthesis.cancel.mockClear();

    await user.click(screen.getByRole('link', { name: /switch language/i }));

    expect(speechSynthesis.cancel).toHaveBeenCalled();
    expect(FakeWebSocket.find('/ws/listen/3/ko')).toBeDefined();
    expect(screen.queryByText('God is love.')).not.toBeInTheDocument();
    const calls = speechSynthesis.speak.mock.calls;
    expect(calls[calls.length - 1][0].lang).toBe('ko-KR');
  });
});

describe('layout', () => {
  it('stacks the translation above the Japanese on a phone and puts them side by side on desktop', () => {
    renderListener('/listen/3/en', { isLive: true });

    const translation = screen.getByTestId('translation-panel');
    const japanese = screen.getByTestId('japanese-panel');

    // Mobile: a single column with the translation first, Japanese below.
    expect(screen.getByTestId('panels').className).toContain('flex-col');
    expect(translation.className).toContain('order-1');
    expect(japanese.className).toContain('order-2');
    // Desktop: two side-by-side panes that ignore the mobile order.
    expect(screen.getByTestId('panels').className).toContain('md:grid-cols-2');
    expect(translation.className).toContain('md:order-none');
    expect(japanese.className).toContain('md:order-none');
  });

  it('gives the translation the larger share of the phone screen', () => {
    renderListener('/listen/3/en', { isLive: true });

    expect(screen.getByTestId('translation-panel').className).toContain('flex-[3]');
    expect(screen.getByTestId('japanese-panel').className).toContain('flex-[2]');
  });
});

describe('reading a previous line', () => {
  it('follows the newest line but does not yank a guest who scrolled back', () => {
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');
    const scroll = screen.getByTestId('translation-scroll');
    Object.defineProperty(scroll, 'scrollHeight', { configurable: true, value: 1000 });
    Object.defineProperty(scroll, 'clientHeight', { configurable: true, value: 300 });

    scroll.scrollTop = 700; // at the bottom
    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '一つ目', translation: 'First line' },
      })
    );
    expect(scroll.scrollTop).toBe(1000);

    scroll.scrollTop = 0; // reading back through the sermon
    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '二つ目', translation: 'Second line' },
      })
    );
    expect(scroll.scrollTop).toBe(0);

    scroll.scrollTop = 650; // back near the bottom
    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '三つ目', translation: 'Third line' },
      })
    );
    expect(scroll.scrollTop).toBe(1000);
  });
});

describe('an in-progress line', () => {
  it('shows the interim transcript, never speaks it, and replaces it when the line finalizes', async () => {
    const user = userEvent.setup();
    renderListener('/listen/3/en', { isLive: true });
    const socket = FakeWebSocket.find('/ws/listen/3/en');
    await user.click(screen.getByRole('button', { name: /audio: off/i }));
    const spokenBeforeInterim = speechSynthesis.speak.mock.calls.length;

    act(() =>
      socket.receive({
        type: 'interim_translation',
        data: { original: '神は語って', translation: 'God is speaking' },
      })
    );

    expect(screen.getByTestId('translation-panel')).toHaveTextContent('God is speaking');
    expect(screen.getByTestId('japanese-panel')).toHaveTextContent('神は語って');
    expect(speechSynthesis.speak.mock.calls.length).toBe(spokenBeforeInterim);

    act(() =>
      socket.receive({
        type: 'live_translation',
        data: { original: '神は語っています。', translation: 'God is speaking now.' },
      })
    );

    expect(screen.queryByText('God is speaking')).not.toBeInTheDocument();
    expect(screen.getByTestId('translation-panel')).toHaveTextContent('God is speaking now.');
  });
});
