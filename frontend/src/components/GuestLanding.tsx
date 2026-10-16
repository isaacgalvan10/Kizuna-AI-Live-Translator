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
      <div className="flex items-center justify-center min-h-screen p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-8 sm:p-12 w-full max-w-md border border-slate-100 text-center space-y-4">
          <h1 className="text-4xl font-black tracking-tight text-indigo-600">絆 KIZUNA</h1>
          <p
            role="alert"
            className="text-sm font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3"
          >
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!guest) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-8 sm:p-12 w-full max-w-md border border-slate-100 text-center space-y-4">
          <h1 className="text-4xl font-black tracking-tight text-indigo-600">絆 KIZUNA</h1>
          <p className="text-sm text-slate-500 font-bold uppercase tracking-widest">
            Connecting to your church…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-8 sm:p-12 w-full max-w-md border border-slate-100">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-black tracking-tight text-indigo-600 mb-2">絆 KIZUNA</h1>
          <p className="text-lg font-bold text-slate-900">{guest.church_name}</p>
          <p className="text-sm text-slate-500 font-bold uppercase tracking-widest mt-1">
            Choose your language
          </p>
        </div>

        {!guest.is_live && (
          <p className="text-sm font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-6 text-center">
            The service hasn't started yet — pick a language now and you'll wait on the
            next screen until the operator begins.
          </p>
        )}

        <div className="space-y-4">
          {LANGUAGES.map((language) => (
            <button
              key={language.code}
              onClick={() => pickLanguage(language.code)}
              className="w-full py-5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-black rounded-2xl transition-all shadow-lg shadow-indigo-200 text-xl tracking-wide"
            >
              {language.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
