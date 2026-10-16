import { useState, useRef } from 'react';

interface PreacherDashboardProps {
  roomId: string;
}

export function PreacherDashboard({ roomId }: PreacherDashboardProps) {
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [status, setStatus] = useState('Ready to broadcast');
  
  const ws = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const startBroadcast = async () => {
    try {
      setStatus('Connecting to server...');
      // 1. Establish the publisher WebSocket connection
      ws.current = new WebSocket(`ws://localhost:8000/ws/stream/${roomId}`);
      
      ws.current.onopen = async () => {
        setStatus('Server connected. Accessing microphone...');
        try {
          // 2. Request microphone access
          const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true
            } 
          });
          streamRef.current = stream;

          // 3. Initialize AudioContext at 16kHz (matching Azure's expected format)
          const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          const audioContext = new AudioContextClass({ sampleRate: 16000 });
          audioContextRef.current = audioContext;

          const source = audioContext.createMediaStreamSource(stream);
          
          // 4. Create a processing node to capture raw audio blocks
          // Buffer size of 4096 frames balances latency and processing performance smoothly
          const processorNode = audioContext.createScriptProcessor(4096, 1, 1);
          processorNodeRef.current = processorNode;

          processorNode.onaudioprocess = (e) => {
            if (ws.current?.readyState !== WebSocket.OPEN) return;

            // Grab the raw float32 single-channel data [-1.0, 1.0]
            const inputData = e.inputBuffer.getChannelData(0);
            
            // Convert to 16-bit signed integers [-32768, 32767]
            const pcmBuffer = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              // Clamp values to protect audio stability
              const s = Math.max(-1, Math.min(1, inputData[i]));
              pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Send the raw binary array directly over the WebSocket
            ws.current.send(pcmBuffer.buffer);
          };

          // Link the audio nodes together
          source.connect(processorNode);
          processorNode.connect(audioContext.destination);

          setIsBroadcasting(true);
          setStatus('🎙️ Live broadcasting and translating!');
        } catch (micErr) {
          console.error(micErr);
          setStatus('Error: Microphone access denied.');
          ws.current?.close();
        }
      };

      ws.current.onclose = () => {
        stopBroadcastState();
        setStatus('Disconnected from server.');
      };

    } catch (err) {
      console.error(err);
      setStatus('Failed to initiate broadcast.');
    }
  };

  const stopBroadcastState = () => {
    // Teardown the audio capture hardware cleanly
    processorNodeRef.current?.disconnect();
    audioContextRef.current?.close();
    streamRef.current?.getTracks().forEach(track => track.stop());
    
    processorNodeRef.current = null;
    audioContextRef.current = null;
    streamRef.current = null;
    setIsBroadcasting(false);
  };


  const stopBroadcast = () => {
    setStatus('Stopping broadcast...');
    
    // Safely close the websocket if it's still open
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.close();
    }
    
    // FORCE the hardware teardown immediately
    stopBroadcastState(); 
  };

  return (
    <div style={{ padding: '1.5rem', background: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <h3>Preacher / Admin Broadcast Panel</h3>
      <p>Room Identifier: <strong>{roomId}</strong></p>
      <p style={{ color: isBroadcasting ? 'green' : '#666', fontWeight: 'bold' }}>Status: {status}</p>
      
      {!isBroadcasting ? (
        <button onClick={startBroadcast} style={{ padding: '0.75rem 1.5rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          Start Live Sermon
        </button>
      ) : (
        <button onClick={stopBroadcast} style={{ padding: '0.75rem 1.5rem', background: '#dc3545', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          End Sermon
        </button>
      )}
    </div>
  );
}