import { useCallback, useEffect, useState } from 'react';
import { cleanTextForSpeech, selectBestSpeechVoice } from '../utils/speechUtils';

export function useSpeechSynthesis(selectedVoiceName: string) {
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [isVoiceSamplePlaying, setIsVoiceSamplePlaying] = useState(false);

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setSpeakingMessageId(null);
    setIsVoiceSamplePlaying(false);
  }, []);

  const handleToggleSpeak = useCallback(
    (text: string, id: string) => {
      if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
        return;
      }
      if (speakingMessageId === id) {
        window.speechSynthesis.cancel();
        setSpeakingMessageId(null);
        return;
      }
      window.speechSynthesis.cancel();
      const clean = cleanTextForSpeech(text);
      if (!clean) return;

      const utterance = new SpeechSynthesisUtterance(clean);
      const allVoices = window.speechSynthesis.getVoices();
      const voice = selectBestSpeechVoice(allVoices, selectedVoiceName);

      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = 'en-US';
      }

      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      utterance.onend = () => setSpeakingMessageId(null);
      utterance.onerror = () => setSpeakingMessageId(null);
      setSpeakingMessageId(id);
      window.speechSynthesis.speak(utterance);
    },
    [speakingMessageId, selectedVoiceName]
  );

  const handleTestVoiceSample = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    if (isVoiceSamplePlaying) {
      window.speechSynthesis.cancel();
      setIsVoiceSamplePlaying(false);
      return;
    }
    window.speechSynthesis.cancel();
    const sample = 'Hello! I am your RAISE AI assistant. This is a preview of the selected voice.';
    const utterance = new SpeechSynthesisUtterance(sample);
    const allVoices = window.speechSynthesis.getVoices();
    const voice = selectBestSpeechVoice(allVoices, selectedVoiceName);

    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else {
      utterance.lang = 'en-US';
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onend = () => setIsVoiceSamplePlaying(false);
    utterance.onerror = () => setIsVoiceSamplePlaying(false);
    setIsVoiceSamplePlaying(true);
    window.speechSynthesis.speak(utterance);
  }, [isVoiceSamplePlaying, selectedVoiceName]);

  return {
    speakingMessageId,
    setSpeakingMessageId,
    isVoiceSamplePlaying,
    setIsVoiceSamplePlaying,
    handleToggleSpeak,
    handleTestVoiceSample,
    stopSpeaking,
  };
}
