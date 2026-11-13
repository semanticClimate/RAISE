import type { ChatMessage, QuestionVersion, ResponseVersion } from '../../../types';

export {
  cleanTextForSpeech,
  computeVoiceWaveScale,
  filterNaturalVoices,
  ROBOTIC_VOICE_NAMES,
  selectBestSpeechVoice,
} from '../../../utils/speechUtils';

export const getTurnQuestionVersions = (
  userMsg: ChatMessage,
  assistantMsg?: ChatMessage
): QuestionVersion[] => {
  if (userMsg.questionVersions && userMsg.questionVersions.length > 0) {
    return userMsg.questionVersions;
  }
  if (assistantMsg?.questionVersions && assistantMsg.questionVersions.length > 0) {
    return assistantMsg.questionVersions;
  }
  const extractedAssistantText =
    (assistantMsg && assistantMsg.role === 'assistant'
      ? assistantMsg.text ||
        (assistantMsg as any).content ||
        assistantMsg.response?.grounded_answer ||
        assistantMsg.response?.answer ||
        assistantMsg.response?.reply ||
        assistantMsg.response?.response ||
        assistantMsg.response?.text ||
        assistantMsg.response?.message ||
        assistantMsg.response?.content ||
        assistantMsg.response?.output ||
        ''
      : '');

  const idSuffix = userMsg.created_at || (userMsg as any).id || 'orig';
  const initialResp: ResponseVersion = {
    id: `resp-init-${idSuffix}`,
    text: extractedAssistantText,
    content: extractedAssistantText,
    response:
      assistantMsg && assistantMsg.role === 'assistant' ? assistantMsg.response : undefined,
    durationSec: assistantMsg?.durationSec,
    timestamp: 'Original',
  };
  return [
    {
      id: `qver-init-${idSuffix}`,
      question: userMsg.text || (userMsg as any).content || '',
      responseVersions: [initialResp],
      currentResponseVersionIndex: 0,
      timestamp: 'Original',
    },
  ];
};
