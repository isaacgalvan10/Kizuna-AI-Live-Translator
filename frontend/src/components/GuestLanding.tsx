import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import api from '../api';

interface GuestJoin {
  status: string;
  user_id: number;
  church_name: string;
  is_live: boolean;
  room_id: number | null;
}

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ko', label: '한국어 (Korean)' },
  { code: 'zh-hans', label: '中文 (Chinese)' },
];

const CARD =
  'w-full max-w-[390px] text-center bg-sand-card border border-line rounded-3xl px-7 py-9';
const BRAND_MARK = 'font-serif text-[32px] font-bold tracking-[0.01em] text-brand';
const SEAM =
  'mx-auto mt-2.5 h-px w-16 bg-linear-to-r from-transparent via-brand/85 to-transparent';
const EYEBROW = 'text-[11px] font-bold uppercase tracking-[0.18em] text-dim';
const LANGUAGE_BUTTON =
  'w-full cursor-pointer rounded-2xl border border-btn-border bg-linear-to-b from-btn to-btn-deep py-[17px] text-[19px] font-extrabold tracking-[0.02em] text-btn-ink transition-[filter] duration-150 hover:brightness-[1.08] active:brightness-[0.94] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand/55';

export default function GuestLanding() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const qr = searchParams.get('qr');

  const [guest, setGuest] = useState<GuestJoin | null>(null);
  const [error, setError] = useState<string | null>(
    qr ? null : "Open this page by scanning your church's QR code."
  );

  useEffect(() => {
    if (!qr) return;
    let cancelled = false;

    api
      .post(`/api/join/${encodeURIComponent(qr)}`)
      .then((response) => {
        if (cancelled) return;
        const join = response.data as GuestJoin;
        if (join.room_id === null) {
          setError(
            'This church has no room set up yet. Ask a staff member to finish setup.'
          );
          return;
        }
        setGuest(join);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          isAxiosError(err) && err.response?.status === 404
            ? "This QR code isn't linked to a church. Ask a staff member for the church's QR code."
            : 'Could not reach the server. Check your connection and try again.'
        );
      });

    return () => {
      cancelled = true;
    };
  }, [qr]);

  const pickLanguage = (lang: string) => {
    if (!guest || guest.room_id === null) return;
    navigate(`/listen/${guest.room_id}/${lang}`, { state: { isLive: guest.is_live } });
  };

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen p-5">
        <div className={`${CARD} space-y-4`}>
          <div>
            <h1 className={BRAND_MARK}>絆 KIZUNA</h1>
            <div className={SEAM} aria-hidden="true" />
          </div>
          <p
            role="alert"
            className="text-sm font-bold text-danger-ink bg-danger-soft border border-danger-line rounded-xl px-4 py-3"
          >
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!guest) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-5 text-center">
        <h1 className="font-serif text-[34px] font-bold tracking-[0.01em] text-brand">
          絆 KIZUNA
        </h1>
        <p className={`${EYEBROW} mt-4.5`}>Connecting to your church…</p>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-5">
      <div className={CARD}>
        <h1 className={BRAND_MARK}>絆 KIZUNA</h1>
        <div className={SEAM} aria-hidden="true" />
        <p className="mt-3.5 font-serif text-[17px] font-bold text-ink">
          {guest.church_name}
        </p>
        <p className={`${EYEBROW} mt-1`}>Choose your language</p>

        {!guest.is_live && (
          <p className="mt-5 mb-1.5 rounded-xl border border-paused-line bg-paused-soft px-3.5 py-3 text-[13px] font-medium leading-normal text-paused-ink">
            The service hasn't started yet — pick a language now and you'll wait on the
            next screen until the operator begins.
          </p>
        )}

        <div className="mt-4.5 flex flex-col gap-3.5">
          {LANGUAGES.map((language) => (
            <button
              key={language.code}
              onClick={() => pickLanguage(language.code)}
              className={LANGUAGE_BUTTON}
            >
              {language.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
