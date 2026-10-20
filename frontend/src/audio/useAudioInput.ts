import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Pcm16Resampler,
  TARGET_SAMPLE_RATE,
  audioConstraints,
  inputLevel,
  loadAudioInputSettings,
  saveAudioInputSettings,
  toAudioDevices,
} from './audioInput';
import type {
  AudioInputDevice,
  AudioInputMode,
  AudioInputSettings,
} from './audioInput';

export type AudioInputStatus = 'idle' | 'requesting' | 'ready' | 'denied' | 'error';

const METER_INTERVAL_MS = 100;
const BROWSER_SUPPORT_ERROR =
  'This browser cannot access audio inputs. Try a current version of Chrome or Edge.';

function createAudioContext(): AudioContext {
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  try {
    return new Ctor({ sampleRate: TARGET_SAMPLE_RATE });
  } catch {
    // Firefox can refuse an unsupported rate; capture at the device's rate and
    // let the resampler do the conversion instead.
    return new Ctor();
  }
}

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) {
    track.onended = null;
    track.stop();
  }
}

export interface AudioInputController {
  settings: AudioInputSettings;
  devices: AudioInputDevice[];
  status: AudioInputStatus;
  error: string | null;
  notice: string | null;
  level: number;
  capturedSampleRate: number | null;
  selectDevice: (deviceId: string | null) => void;
  selectMode: (mode: AudioInputMode) => void;
  retry: () => void;
  beginCapture: (onPcm: (pcm: Int16Array<ArrayBuffer>) => void) => Promise<void>;
  endCapture: () => void;
}

// Owns the operator's microphone permissions and input graph. The same graph
// feeds the pre-Start level meter and, once Start is pressed, the WebSocket:
// one stream, one AudioContext, one source — so what the meter shows is exactly
// what the backend hears.
export function useAudioInput(enabled: boolean): AudioInputController {
  const [settings, setSettings] = useState<AudioInputSettings>(loadAudioInputSettings);
  const [devices, setDevices] = useState<AudioInputDevice[]>([]);
  const [status, setStatus] = useState<AudioInputStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const [capturedSampleRate, setCapturedSampleRate] = useState<number | null>(null);

  const settingsRef = useRef(settings);
  const enabledRef = useRef(enabled);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const resamplerRef = useRef<Pcm16Resampler | null>(null);
  const onPcmRef = useRef<((pcm: Int16Array<ArrayBuffer>) => void) | null>(null);
  const meterTimerRef = useRef<number | null>(null);
  const meterBufferRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const generationRef = useRef(0);
  const deviceLostRef = useRef<() => void>(() => {});

  const updateSettings = useCallback((next: AudioInputSettings, persist = true) => {
    settingsRef.current = next;
    setSettings(next);
    if (persist) saveAudioInputSettings(next);
  }, []);

  const stopMeter = useCallback(() => {
    if (meterTimerRef.current !== null) {
      window.clearInterval(meterTimerRef.current);
      meterTimerRef.current = null;
    }
  }, []);

  const teardownGraph = useCallback(
    (stopStream: boolean) => {
      processorRef.current?.disconnect();
      processorRef.current = null;
      resamplerRef.current = null;
      analyserRef.current?.disconnect();
      analyserRef.current = null;
      sourceRef.current?.disconnect();
      sourceRef.current = null;

      if (stopStream && streamRef.current) {
        stopTracks(streamRef.current);
        streamRef.current = null;
      }
      if (stopStream) {
        stopMeter();
        setLevel(0);
      }
    },
    [stopMeter]
  );

  const release = useCallback(() => {
    generationRef.current++;
    teardownGraph(true);
    const context = contextRef.current;
    contextRef.current = null;
    if (context && context.state !== 'closed') void context.close();
    setCapturedSampleRate(null);
  }, [teardownGraph]);

  const startMeter = useCallback(() => {
    if (meterTimerRef.current !== null) return;
    meterTimerRef.current = window.setInterval(() => {
      const analyser = analyserRef.current;
      if (!analyser) return;
      if (!meterBufferRef.current || meterBufferRef.current.length !== analyser.fftSize) {
        meterBufferRef.current = new Float32Array(analyser.fftSize);
      }
      analyser.getFloatTimeDomainData(meterBufferRef.current);
      setLevel(inputLevel(meterBufferRef.current));
    }, METER_INTERVAL_MS);
  }, []);

  const attachProcessor = useCallback(() => {
    const context = contextRef.current;
    const source = sourceRef.current;
    if (!context || !source || processorRef.current) return;

    const node = context.createScriptProcessor(4096, 1, 1);
    const resampler = new Pcm16Resampler(context.sampleRate);
    resamplerRef.current = resampler;
    node.onaudioprocess = (event: AudioProcessingEvent) => {
      const pcm = resampler.process(event.inputBuffer.getChannelData(0));
      if (pcm.length > 0) onPcmRef.current?.(pcm);
    };
    source.connect(node);
    node.connect(context.destination);
    processorRef.current = node;
  }, []);

  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    const listed = await navigator.mediaDevices.enumerateDevices();
    const next = toAudioDevices(listed);
    setDevices(next);
    return next;
  }, []);

  const acquire = useCallback(async (): Promise<boolean> => {
    if (!enabledRef.current) return false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('error');
      setError(BROWSER_SUPPORT_ERROR);
      return false;
    }

    const current = streamRef.current;
    if (current?.getAudioTracks().every((track) => track.readyState === 'ended')) {
      teardownGraph(true);
    }

    const generation = ++generationRef.current;
    setStatus('requesting');

    let requested = settingsRef.current;
    let stream: MediaStream | null = null;

    for (let attempt = 0; attempt < 2 && !stream; attempt++) {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints(requested),
        });
      } catch (err) {
        if (generation !== generationRef.current) return false;

        const name = (err as { name?: string }).name;
        const deviceMissing =
          requested.deviceId !== null &&
          (name === 'OverconstrainedError' || name === 'NotFoundError');
        if (deviceMissing && attempt === 0) {
          requested = { ...requested, deviceId: null };
          // The saved selection survives the fallback so a reload, or the next
          // visit, tries the operator's device again.
          updateSettings(requested, false);
          setNotice('The selected input device is unavailable. Using the system default input.');
          continue;
        }

        if (name === 'NotAllowedError' || name === 'SecurityError') {
          setStatus('denied');
          setError(
            'Microphone access was denied. Allow microphone access in the browser, then retry.'
          );
        } else {
          setStatus('error');
          setError('Could not open the selected audio input. Check the connection, then retry.');
        }
        return false;
      }
    }
    if (!stream) return false;

    if (generation !== generationRef.current) {
      stopTracks(stream);
      return false;
    }

    let context = contextRef.current;
    if (!context || context.state === 'closed') {
      try {
        context = createAudioContext();
      } catch {
        stopTracks(stream);
        setStatus('error');
        setError('Could not capture audio. Try a current version of Chrome or Edge.');
        return false;
      }
      contextRef.current = context;
    }
    if (context.state === 'suspended') void context.resume().catch(() => {});
    setCapturedSampleRate(context.sampleRate);

    const captureActive = onPcmRef.current !== null;
    teardownGraph(true);
    streamRef.current = stream;

    const track = stream.getAudioTracks()[0];
    if (track) {
      track.onended = () => {
        if (streamRef.current === stream) streamRef.current = null;
        deviceLostRef.current();
      };
    }

    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    sourceRef.current = source;
    analyserRef.current = analyser;
    startMeter();
    if (captureActive) attachProcessor();

    await refreshDevices().catch(() => {
      // Keep the previous list; the input itself is already working.
    });
    if (generation !== generationRef.current) return false;

    setStatus('ready');
    setError(null);
    return true;
  }, [attachProcessor, refreshDevices, startMeter, teardownGraph, updateSettings]);

  const handleDeviceLost = useCallback(() => {
    if (!enabledRef.current) return;
    const selected = settingsRef.current.deviceId;
    setNotice(
      selected
        ? 'The selected input device disconnected. Falling back to the system default input. Reconnect it, then choose it again.'
        : 'The audio input disconnected. Falling back to the system default input.'
    );
    setError(null);
    if (selected) updateSettings({ ...settingsRef.current, deviceId: null }, false);
    void acquire();
  }, [acquire, updateSettings]);

  useEffect(() => {
    deviceLostRef.current = handleDeviceLost;
  }, [handleDeviceLost]);

  useEffect(() => {
    if (!enabled) return;
    const mediaDevices = navigator.mediaDevices;
    if (!mediaDevices?.addEventListener) return;

    const onChange = () => {
      refreshDevices()
        .then((next) => {
          const selected = settingsRef.current.deviceId;
          if (selected && !next.some((device) => device.id === selected)) {
            handleDeviceLost();
          }
        })
        .catch(() => {
          // A failed enumeration needs no reaction; the next change retries.
        });
    };
    mediaDevices.addEventListener('devicechange', onChange);
    return () => mediaDevices.removeEventListener('devicechange', onChange);
  }, [enabled, refreshDevices, handleDeviceLost]);

  useEffect(() => {
    enabledRef.current = enabled;
    if (!enabled) return;
    // Deferred so the effect body only subscribes to the microphone; acquire
    // publishes its first state after this render commits.
    queueMicrotask(() => {
      void acquire();
    });
    return () => {
      enabledRef.current = false;
      release();
    };
  }, [enabled, acquire, release]);

  const applySettings = useCallback(
    (next: AudioInputSettings) => {
      setNotice(null);
      updateSettings(next);
      if (enabledRef.current) void acquire();
    },
    [acquire, updateSettings]
  );

  const selectDevice = useCallback(
    (deviceId: string | null) => {
      applySettings({ ...settingsRef.current, deviceId });
    },
    [applySettings]
  );

  const selectMode = useCallback(
    (mode: AudioInputMode) => {
      applySettings({ ...settingsRef.current, mode });
    },
    [applySettings]
  );

  const retry = useCallback(() => {
    setNotice(null);
    void acquire();
  }, [acquire]);

  const beginCapture = useCallback(
    async (onPcm: (pcm: Int16Array<ArrayBuffer>) => void) => {
      onPcmRef.current = onPcm;
      if (!streamRef.current) {
        const ready = await acquire();
        if (!ready) {
          onPcmRef.current = null;
          throw new Error('audio input unavailable');
        }
      }

      // The preview context may be suspended by the browser's autoplay policy
      // until a gesture. Start is that gesture, so resume before attaching.
      const context = contextRef.current;
      if (!context) {
        onPcmRef.current = null;
        throw new Error('audio context unavailable');
      }
      if (context.state !== 'running') {
        try {
          await context.resume();
        } catch {
          // Reported below when the state is still not running.
        }
      }
      if (context.state !== 'running') {
        onPcmRef.current = null;
        setStatus('error');
        setError('The browser blocked audio input. Press Start again and allow audio for this site.');
        throw new Error('audio context is not running');
      }

      setError(null);
      attachProcessor();
    },
    [acquire, attachProcessor]
  );

  const endCapture = useCallback(() => {
    onPcmRef.current = null;
    processorRef.current?.disconnect();
    processorRef.current = null;
    resamplerRef.current = null;
  }, []);

  return {
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
    beginCapture,
    endCapture,
  };
}
