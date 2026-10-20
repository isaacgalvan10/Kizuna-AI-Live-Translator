import { describe, expect, it, vi } from 'vitest';
import {
  AUDIO_INPUT_STORAGE_KEY,
  DEFAULT_AUDIO_INPUT_SETTINGS,
  Pcm16Resampler,
  TARGET_SAMPLE_RATE,
  audioConstraints,
  inputLevel,
  loadAudioInputSettings,
  saveAudioInputSettings,
  toAudioDevices,
} from './audioInput';
import type { AudioInputSettings } from './audioInput';

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    removeItem: vi.fn((key: string) => values.delete(key)),
    clear: vi.fn(() => values.clear()),
    key: vi.fn(() => null),
    get length() {
      return values.size;
    },
  } as unknown as Storage;
}

const MIXER: AudioInputSettings = { deviceId: 'usb-mixer-1', mode: 'mixer' };

describe('audio input settings', () => {
  it('starts on the mixer mode and the system default device', () => {
    expect(loadAudioInputSettings(memoryStorage())).toEqual(DEFAULT_AUDIO_INPUT_SETTINGS);
    expect(DEFAULT_AUDIO_INPUT_SETTINGS).toEqual({ deviceId: null, mode: 'mixer' });
  });

  it('round-trips the operator selection through storage', () => {
    const storage = memoryStorage();
    saveAudioInputSettings(MIXER, storage);

    expect(storage.setItem).toHaveBeenCalledWith(
      AUDIO_INPUT_STORAGE_KEY,
      JSON.stringify(MIXER)
    );
    expect(loadAudioInputSettings(storage)).toEqual(MIXER);
  });

  it('ignores malformed stored data instead of breaking the console', () => {
    expect(loadAudioInputSettings(memoryStorage({ [AUDIO_INPUT_STORAGE_KEY]: '{nope' }))).toEqual(
      DEFAULT_AUDIO_INPUT_SETTINGS
    );
    expect(
      loadAudioInputSettings(
        memoryStorage({ [AUDIO_INPUT_STORAGE_KEY]: JSON.stringify({ mode: 'something-else' }) })
      )
    ).toEqual(DEFAULT_AUDIO_INPUT_SETTINGS);
  });

  it('survives a browser that refuses storage access', () => {
    const storage = memoryStorage();
    storage.getItem = vi.fn(() => {
      throw new Error('storage disabled');
    });
    storage.setItem = vi.fn(() => {
      throw new Error('storage disabled');
    });

    expect(loadAudioInputSettings(storage)).toEqual(DEFAULT_AUDIO_INPUT_SETTINGS);
    expect(() => saveAudioInputSettings(MIXER, storage)).not.toThrow();
  });
});

describe('audio input constraints', () => {
  it('keeps browser speech processing on for the laptop microphone', () => {
    expect(audioConstraints({ deviceId: null, mode: 'microphone' })).toEqual({
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    });
  });

  it('turns browser speech processing off for a mixer or line input', () => {
    expect(audioConstraints({ deviceId: null, mode: 'mixer' })).toEqual({
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
  });

  it('pins the selected device exactly and leaves the default unconstrained', () => {
    expect(audioConstraints(MIXER)).toMatchObject({ deviceId: { exact: 'usb-mixer-1' } });
    expect(audioConstraints({ deviceId: null, mode: 'mixer' })).not.toHaveProperty('deviceId');
  });
});

describe('audio input device list', () => {
  it('keeps only audio inputs and gives unlabeled devices a readable name', () => {
    const devices = [
      { deviceId: 'mic-1', kind: 'audioinput', label: 'Built-in Microphone' },
      { deviceId: 'speaker-1', kind: 'audiooutput', label: 'Speakers' },
      { deviceId: 'mic-2', kind: 'audioinput', label: '' },
    ];

    expect(toAudioDevices(devices)).toEqual([
      { id: 'mic-1', label: 'Built-in Microphone' },
      { id: 'mic-2', label: 'Microphone 2' },
    ]);
  });
});

describe('Pcm16Resampler', () => {
  it('passes 16 kHz audio through as clamped 16-bit PCM', () => {
    const resampler = new Pcm16Resampler(TARGET_SAMPLE_RATE);
    const pcm = resampler.process(new Float32Array([0.5, -0.5, 2, -2]));

    expect(Array.from(pcm)).toEqual([16384, -16384, 32767, -32768]);
  });

  it('resamples a 48 kHz capture down to 16 kHz with the same duration', () => {
    const resampler = new Pcm16Resampler(48000);
    const halfSecondAt48k = new Float32Array(24000).fill(0.5);

    const pcm = resampler.process(halfSecondAt48k);

    expect(pcm.length).toBeGreaterThan(7900);
    expect(pcm.length).toBeLessThan(8100);
    expect(pcm[100]).toBe(16384);
  });

  it('keeps a continuous signal continuous across chunk boundaries', () => {
    const resampler = new Pcm16Resampler(48000);
    const first = resampler.process(new Float32Array(4800).fill(0.25));
    const second = resampler.process(new Float32Array(4800).fill(0.25));

    for (const sample of [...first, ...second]) {
      expect(sample).toBe(8192);
    }
  });
});

describe('inputLevel', () => {
  function sine(amplitude: number, samples = 1600): Float32Array {
    const data = new Float32Array(samples);
    for (let i = 0; i < samples; i++) {
      data[i] = amplitude * Math.sin((2 * Math.PI * 440 * i) / TARGET_SAMPLE_RATE);
    }
    return data;
  }

  it('reports silence as an empty meter', () => {
    expect(inputLevel(new Float32Array(1600))).toBe(0);
    expect(inputLevel(new Float32Array(0))).toBe(0);
  });

  it('reports a loud signal near full scale', () => {
    expect(inputLevel(sine(1))).toBeGreaterThan(0.9);
  });

  it('reports a very quiet signal as silent', () => {
    expect(inputLevel(sine(0.0005))).toBe(0);
  });
});
