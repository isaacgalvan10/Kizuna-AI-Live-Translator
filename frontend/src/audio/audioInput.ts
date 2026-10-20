// Everything the operator console needs to know about where its audio comes
// from, kept pure so the device picker's rules can be tested without a browser.
// The backend expects 16 kHz, 16-bit mono PCM; browsers treat the AudioContext
// sample-rate hint as a preference, so capture may need resampling.

export const AUDIO_INPUT_STORAGE_KEY = 'kizuna_audio_input';
export const TARGET_SAMPLE_RATE = 16000;

export type AudioInputMode = 'microphone' | 'mixer';

export interface AudioInputSettings {
  deviceId: string | null;
  mode: AudioInputMode;
}

export interface AudioInputDevice {
  id: string;
  label: string;
}

export interface AudioDeviceLike {
  deviceId: string;
  kind: string;
  label: string;
}

export const DEFAULT_AUDIO_INPUT_SETTINGS: AudioInputSettings = {
  deviceId: null,
  mode: 'mixer',
};

function browserStorage(): Storage | undefined {
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

export function loadAudioInputSettings(
  storage: Storage | undefined = browserStorage()
): AudioInputSettings {
  try {
    const raw = storage?.getItem(AUDIO_INPUT_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_AUDIO_INPUT_SETTINGS };

    const parsed = JSON.parse(raw) as Partial<AudioInputSettings> | null;
    if (!parsed || typeof parsed !== 'object') return { ...DEFAULT_AUDIO_INPUT_SETTINGS };

    const mode =
      parsed.mode === 'microphone' || parsed.mode === 'mixer'
        ? parsed.mode
        : DEFAULT_AUDIO_INPUT_SETTINGS.mode;
    const deviceId = typeof parsed.deviceId === 'string' ? parsed.deviceId : null;
    return { deviceId, mode };
  } catch {
    return { ...DEFAULT_AUDIO_INPUT_SETTINGS };
  }
}

export function saveAudioInputSettings(
  settings: AudioInputSettings,
  storage: Storage | undefined = browserStorage()
): void {
  try {
    storage?.setItem(AUDIO_INPUT_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage can be unavailable (private mode, blocked cookies). The selection
    // still works for this visit; only persistence is lost.
  }
}

// Laptop microphone mode keeps the browser's speech processing on. A mixer or
// line feed is already clean, and those filters would pump, gate, or cancel it.
export function audioConstraints(settings: AudioInputSettings): MediaTrackConstraints {
  const speechProcessing =
    settings.mode === 'mixer'
      ? { echoCancellation: false, noiseSuppression: false, autoGainControl: false }
      : { echoCancellation: true, noiseSuppression: true, autoGainControl: true };

  return {
    ...(settings.deviceId ? { deviceId: { exact: settings.deviceId } } : {}),
    ...speechProcessing,
  };
}

export function toAudioDevices(devices: readonly AudioDeviceLike[]): AudioInputDevice[] {
  return devices
    .filter((device) => device.kind === 'audioinput')
    .map((device, index) => ({
      id: device.deviceId,
      label: device.label || `Microphone ${index + 1}`,
    }));
}

function toPcm16(sample: number): number {
  const clamped = Math.max(-1, Math.min(1, sample));
  // 16-bit PCM is asymmetric: -1 maps to -32768 but +1 only to 32767.
  return Math.round(clamped * (clamped < 0 ? 0x8000 : 0x7fff));
}

// Streaming linear resampler. The previous chunk's last sample is kept as the
// first sample of the next buffer, so a signal that crosses a buffer boundary
// stays continuous instead of clicking.
export class Pcm16Resampler {
  private readonly ratio: number;
  private readonly inputRate: number;
  private tail: number | null = null;
  private position = 0;

  constructor(inputRate: number) {
    this.inputRate = inputRate;
    this.ratio = inputRate / TARGET_SAMPLE_RATE;
  }

  process(input: Float32Array): Int16Array<ArrayBuffer> {
    if (input.length === 0) return new Int16Array(0);

    if (this.inputRate === TARGET_SAMPLE_RATE) {
      const pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) pcm[i] = toPcm16(input[i]);
      return pcm;
    }

    const buffer =
      this.tail === null
        ? input
        : (() => {
            const joined = new Float32Array(input.length + 1);
            joined[0] = this.tail;
            joined.set(input, 1);
            return joined;
          })();

    const output: number[] = [];
    let position = this.position;
    while (position < buffer.length - 1) {
      const index = Math.floor(position);
      const fraction = position - index;
      const sample = buffer[index] * (1 - fraction) + buffer[index + 1] * fraction;
      output.push(toPcm16(sample));
      position += this.ratio;
    }

    this.tail = buffer[buffer.length - 1];
    this.position = position - (buffer.length - 1);

    return Int16Array.from(output);
  }
}

// Normalised 0..1 meter value. A signal needs to clear roughly -60 dBFS to
// register at all, which keeps idle hiss from looking like arriving audio.
export function inputLevel(samples: Float32Array): number {
  if (samples.length === 0) return 0;

  let sumSquares = 0;
  for (const sample of samples) sumSquares += sample * sample;

  const rms = Math.sqrt(sumSquares / samples.length);
  if (rms === 0) return 0;

  const decibels = 20 * Math.log10(rms);
  return Math.max(0, Math.min(1, (decibels + 60) / 60));
}
