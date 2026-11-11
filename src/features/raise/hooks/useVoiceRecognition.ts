import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseVoiceRecognitionOptions {
  query: string;
  setQuery: (q: string) => void;
  onSpeechResultFocus?: () => void;
}

export function useVoiceRecognition({
  query,
  setQuery,
  onSpeechResultFocus,
}: UseVoiceRecognitionOptions) {
  const [isListening, setIsListening] = useState(false);
  const [isVoiceSpeaking, setIsVoiceSpeaking] = useState(false);
  const [voiceAudioLevels, setVoiceAudioLevels] = useState<number[]>([1, 1, 1, 1, 1, 1, 1]);
  const [voiceDurationSec, setVoiceDurationSec] = useState(0);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioAnalyserRef = useRef<AnalyserNode | null>(null);
  const audioAnimFrameRef = useRef<number | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const voiceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const speechTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const baseQueryRef = useRef(query);

  const stopVoiceListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (audioAnimFrameRef.current) {
      cancelAnimationFrame(audioAnimFrameRef.current);
      audioAnimFrameRef.current = null;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    audioAnalyserRef.current = null;
    if (voiceTimerRef.current) {
      clearInterval(voiceTimerRef.current);
      voiceTimerRef.current = null;
    }
    if (speechTimeoutRef.current) {
      clearTimeout(speechTimeoutRef.current);
      speechTimeoutRef.current = null;
    }
    setIsListening(false);
    setIsVoiceSpeaking(false);
    setVoiceAudioLevels([1, 1, 1, 1, 1, 1, 1]);
  }, []);

  const handleToggleVoiceQuery = useCallback(() => {
    if (typeof window === 'undefined') return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setVoiceError(
        'Voice query is not supported in this browser. Please use Chrome, Edge, Safari, or a Chromium browser.'
      );
      setTimeout(() => setVoiceError(null), 5000);
      return;
    }

    if (isListening) {
      stopVoiceListening();
      return;
    }

    if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }

    try {
      setVoiceError(null);
      baseQueryRef.current = query;

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      const triggerSpeaking = (durationMs = 900) => {
        setIsVoiceSpeaking(true);
        if (speechTimeoutRef.current) {
          clearTimeout(speechTimeoutRef.current);
        }
        speechTimeoutRef.current = setTimeout(() => {
          setIsVoiceSpeaking(false);
        }, durationMs);
      };

      recognition.onstart = () => {
        setIsListening(true);
        setIsVoiceSpeaking(false);
        setVoiceDurationSec(0);
        if (voiceTimerRef.current) clearInterval(voiceTimerRef.current);
        voiceTimerRef.current = setInterval(() => {
          setVoiceDurationSec((prev) => prev + 1);
        }, 1000);
      };

      recognition.onspeechstart = () => triggerSpeaking(1200);
      recognition.onspeechend = () => setIsVoiceSpeaking(false);
      recognition.onsoundstart = () => triggerSpeaking(1000);
      recognition.onsoundend = () => setIsVoiceSpeaking(false);
      recognition.onaudiostart = () => triggerSpeaking(800);

      recognition.onresult = (event: any) => {
        triggerSpeaking(1100);
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        const base = baseQueryRef.current.trim();
        const speech = transcript.trim();
        const combined = base ? `${base} ${speech}` : speech;
        setQuery(combined);
        onSpeechResultFocus?.();
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          setVoiceError('Microphone access denied. Please click the permissions icon to allow microphone.');
        } else if (event.error === 'service-not-allowed') {
          setVoiceError('Speech recognition service is blocked by your browser or OS settings.');
        } else if (event.error === 'network') {
          setVoiceError('Speech recognition network service is unreachable.');
        } else if (event.error === 'audio-capture') {
          setVoiceError('No microphone detected or microphone is in use by another app.');
        } else if (event.error !== 'no-speech') {
          setVoiceError(`Speech recognition unavailable (${event.error}).`);
        }
        stopVoiceListening();
        setTimeout(() => setVoiceError(null), 6000);
      };

      recognition.onend = () => {
        stopVoiceListening();
      };

      recognitionRef.current = recognition;
      recognition.start();

      // Web Audio Analyser for frequency visualizer
      if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        navigator.mediaDevices
          .getUserMedia({ audio: true })
          .then((stream) => {
            if (!recognitionRef.current) {
              stream.getTracks().forEach((t) => t.stop());
              return;
            }
            audioStreamRef.current = stream;
            const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
            if (AudioCtx) {
              const ctx = new AudioCtx();
              audioContextRef.current = ctx;
              const source = ctx.createMediaStreamSource(stream);
              const analyser = ctx.createAnalyser();
              analyser.fftSize = 64;
              analyser.smoothingTimeConstant = 0.4;
              source.connect(analyser);
              audioAnalyserRef.current = analyser;

              const bufferLength = analyser.frequencyBinCount;
              const dataArray = new Uint8Array(bufferLength);

              const loop = () => {
                if (!audioAnalyserRef.current) return;
                audioAnalyserRef.current.getByteFrequencyData(dataArray);

                const numBars = 7;
                const step = Math.max(1, Math.floor(bufferLength / numBars));
                const newLevels: number[] = [];
                let sum = 0;

                for (let i = 0; i < numBars; i++) {
                  const val = dataArray[i * step] || 0;
                  sum += val;
                  const normalized = Math.min(1.8, Math.max(0.25, (val / 140) * 1.5));
                  newLevels.push(normalized);
                }

                if (sum / numBars > 12) {
                  triggerSpeaking(500);
                }
                setVoiceAudioLevels(newLevels);
                audioAnimFrameRef.current = requestAnimationFrame(loop);
              };

              audioAnimFrameRef.current = requestAnimationFrame(loop);
            }
          })
          .catch(() => {});
      }
    } catch {
      stopVoiceListening();
    }
  }, [isListening, query, setQuery, onSpeechResultFocus, stopVoiceListening]);

  const formatVoiceDuration = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const rem = seconds % 60;
    return `${mins}:${rem < 10 ? '0' : ''}${rem}`;
  }, []);

  useEffect(() => {
    return () => {
      stopVoiceListening();
    };
  }, [stopVoiceListening]);

  return {
    isListening,
    isVoiceSpeaking,
    voiceAudioLevels,
    voiceDurationSec,
    voiceError,
    setVoiceError,
    handleToggleVoiceQuery,
    stopVoiceListening,
    formatVoiceDuration,
  };
}
