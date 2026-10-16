import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import OperatorConsole from './OperatorConsole';
import api from '../api';

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

function stubAudioCapture() {
  const processor = {
    connect: vi.fn(),
    disconnect: vi.fn(),
    onaudioprocess: null as null | ((event: unknown) => void),
  };
  const context = {
    destination: {},
    createMediaStreamSource: vi.fn(() => ({ connect: vi.fn() })),
    createScriptProcessor: vi.fn(() => processor),
    close: vi.fn(),
  };
  vi.stubGlobal(
    'AudioContext',
    vi.fn(function AudioContextStub() {
      return context;
    })
  );
  Object.defineProperty(window.navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }) },
  });
  return { processor, context };
}

async function renderConsoleWithStoredSession() {
  localStorage.setItem(TOKEN_KEY, 'stored-token');
  mockedGet.mockResolvedValue({ data: CHURCH });
  render(<OperatorConsole />);
  await screen.findByText('Kizuna Test Church');
}

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
