import type { AudioInputMode } from '../audio/audioInput';
import { TARGET_SAMPLE_RATE } from '../audio/audioInput';
import type { AudioInputController, AudioInputStatus } from '../audio/useAudioInput';
import { FOCUS } from '../focus';
import ErrorBanner from './ErrorBanner';

const EYEBROW = 'text-[11px] font-bold uppercase tracking-[0.12em] text-dim';

const MODE_OPTIONS: { value: AudioInputMode; title: string; detail: string }[] = [
  {
    value: 'microphone',
    title: 'Laptop microphone',
    detail: 'Echo cancellation and noise suppression on.',
  },
  {
    value: 'mixer',
    title: 'Mixer / line input',
    detail: 'Raw line input; browser speech processing off.',
  },
];

const AUDIO_THRESHOLD = 0.05;

function statusText(status: AudioInputStatus): string | null {
  if (status === 'ready') return 'Input ready';
  if (status === 'requesting') return 'Checking input…';
  if (status === 'denied' || status === 'error') return 'Input unavailable';
  return null;
}

export default function AudioInputPanel({ audio }: { audio: AudioInputController }) {
  const {
    settings,
    devices,
    status,
    error,
    notice,
    level,
    capturedSampleRate,
    selectDevice,
    selectMode,
    retry,
  } = audio;
  const percent = Math.round(level * 100);
  const hasAudio = level >= AUDIO_THRESHOLD;
  const badge = statusText(status);
  const canRetry = status === 'denied' || status === 'error';
  const labelRate = TARGET_SAMPLE_RATE / 1000;
  const sampleRateText =
    capturedSampleRate === null
      ? null
      : capturedSampleRate === TARGET_SAMPLE_RATE
        ? `Capturing at ${labelRate} kHz.`
        : `Browser captures at ${Math.round(capturedSampleRate / 1000)} kHz; resampling to ${labelRate} kHz.`;

  return (
    <section aria-labelledby="audio-input-heading" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="audio-input-heading" className={EYEBROW}>
          Audio input
        </h2>
        {badge && (
          <span
            className={`rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em] ${
              status === 'ready'
                ? 'border-live-line bg-live-soft text-live-ink'
                : 'border-danger-line bg-danger-soft text-danger-ink'
            }`}
          >
            {badge}
          </span>
        )}
      </div>

      <fieldset>
        <legend className={`mb-2 block ${EYEBROW}`}>Input source</legend>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {MODE_OPTIONS.map((option) => {
            const active = settings.mode === option.value;
            return (
              <label
                key={option.value}
                className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-colors ${
                  active
                    ? 'border-brand-line bg-brand-soft'
                    : 'border-line bg-sand-raise hover:bg-sand-hover'
                }`}
              >
                <input
                  type="radio"
                  name="audio-input-mode"
                  value={option.value}
                  checked={active}
                  onChange={() => selectMode(option.value)}
                  className={`mt-0.5 h-4 w-4 shrink-0 accent-brand ${FOCUS}`}
                />
                <span>
                  <span className="block text-sm font-bold text-ink">{option.title}</span>
                  <span className="mt-0.5 block text-xs leading-[1.4] text-dim">
                    {option.detail}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div>
        <label htmlFor="audio-input-device" className={`mb-2 block ${EYEBROW}`}>
          Input device
        </label>
        <select
          id="audio-input-device"
          value={settings.deviceId ?? ''}
          onChange={(event) => selectDevice(event.target.value || null)}
          className={`w-full rounded-xl border border-line bg-sand-raise px-3.5 py-3 text-sm font-medium text-ink ${FOCUS}`}
        >
          <option value="">System default input</option>
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className={EYEBROW}>Input level</span>
          <span className={`text-xs font-bold ${hasAudio ? 'text-live-ink' : 'text-dim'}`}>
            {hasAudio ? 'Audio detected' : 'No audio'}
          </span>
        </div>
        <div
          role="meter"
          aria-label="Input level"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="h-2.5 overflow-hidden rounded-full border border-line-soft bg-sand-deep"
        >
          <div
            className={`h-full rounded-full transition-[width] duration-100 ${
              hasAudio ? 'bg-live' : 'bg-mute'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>
        {sampleRateText && <p className="mt-2 text-xs text-dim">{sampleRateText}</p>}
      </div>

      {notice && (
        <p
          role="alert"
          className="rounded-xl border border-paused-line bg-paused-soft px-4 py-3 text-sm font-bold text-paused-ink"
        >
          {notice}
        </p>
      )}

      {error && <ErrorBanner message={error} />}

      {canRetry && (
        <button
          type="button"
          onClick={retry}
          className={`cursor-pointer rounded-xl border border-ink bg-ink px-4 py-2.5 text-[13px] font-bold text-sand-raise transition-[filter] duration-150 hover:brightness-[1.15] ${FOCUS}`}
        >
          Retry audio input
        </button>
      )}
    </section>
  );
}
