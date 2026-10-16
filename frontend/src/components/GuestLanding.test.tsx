import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import GuestLanding from './GuestLanding';
import api from '../api';

vi.mock('../api', () => ({
  default: { post: vi.fn() },
}));

const mockedPost = api.post as unknown as Mock;

const LIVE_JOIN = {
  status: 'success',
  user_id: 11,
  church_name: 'Kizuna Test Church',
  is_live: true,
  room_id: 3,
};

function ListenProbe() {
  const { roomId, lang } = useParams();
  const location = useLocation();
  const isLive = (location.state as { isLive?: boolean } | null)?.isLive;
  return (
    <div data-testid="listen-probe">
      {roomId}|{lang}|{String(isLive)}
    </div>
  );
}

function renderLanding(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<GuestLanding />} />
        <Route path="/listen/:roomId/:lang" element={<ListenProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('a scanned QR code', () => {
  it('joins the church and offers the language picker without operator controls', async () => {
    mockedPost.mockResolvedValue({ data: LIVE_JOIN });

    renderLanding('/?qr=test-hash-123');

    expect(await screen.findByText('Kizuna Test Church')).toBeInTheDocument();
    expect(mockedPost).toHaveBeenCalledWith('/api/join/test-hash-123');
    expect(screen.getByRole('button', { name: /english/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /korean/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /chinese/i })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /broadcaster|dashboard/i })
    ).not.toBeInTheDocument();
  });

  it('sends a live guest to the listener view in the picked language', async () => {
    const user = userEvent.setup();
    mockedPost.mockResolvedValue({ data: LIVE_JOIN });

    renderLanding('/?qr=test-hash-123');
    await user.click(await screen.findByRole('button', { name: /korean/i }));

    expect(screen.getByTestId('listen-probe')).toHaveTextContent('3|ko|true');
  });

  it('lets a guest pick a language before the feed starts, then wait', async () => {
    const user = userEvent.setup();
    mockedPost.mockResolvedValue({ data: { ...LIVE_JOIN, is_live: false } });

    renderLanding('/?qr=test-hash-123');

    expect(await screen.findByText(/hasn't started/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /chinese/i }));

    expect(screen.getByTestId('listen-probe')).toHaveTextContent('3|zh-hans|false');
  });
});

describe('a bad scan', () => {
  it('rejects an unknown QR hash', async () => {
    mockedPost.mockRejectedValue(
      Object.assign(new Error('Not Found'), {
        isAxiosError: true,
        response: { status: 404 },
      })
    );

    renderLanding('/?qr=unknown-hash');

    expect(await screen.findByRole('alert')).toHaveTextContent(/isn't linked to a church/i);
    expect(screen.queryByRole('button', { name: /english/i })).not.toBeInTheDocument();
  });

  it('reports an unreachable server separately from a bad QR code', async () => {
    mockedPost.mockRejectedValue(
      Object.assign(new Error('Network Error'), {
        isAxiosError: true,
        response: undefined,
      })
    );

    renderLanding('/?qr=test-hash-123');

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the server/i);
  });

  it('explains when the URL carries no QR code', () => {
    renderLanding('/');

    expect(screen.getByRole('alert')).toHaveTextContent(/scanning your church's qr code/i);
    expect(mockedPost).not.toHaveBeenCalled();
  });

  it('explains when the church has no room yet', async () => {
    mockedPost.mockResolvedValue({ data: { ...LIVE_JOIN, room_id: null } });

    renderLanding('/?qr=test-hash-123');

    expect(await screen.findByRole('alert')).toHaveTextContent(/no room set up/i);
    expect(screen.queryByRole('button', { name: /english/i })).not.toBeInTheDocument();
  });
});
