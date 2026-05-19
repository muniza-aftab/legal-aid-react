import { useAppStore } from '@/services/store'
import { useT, isRTL } from '@/services/i18n'
import { SectionHeader } from '@/components/ui/index'
import ChatAssistant from '@/components/chat/ChatAssistant'

export default function ChatPage() {
  const t = useT()
  const { language, analysisResult } = useAppStore()
  const rtl = isRTL(language)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6" dir={rtl ? 'rtl' : 'ltr'}>
      <SectionHeader
        eyebrow={t('chat_eyebrow')}
        title={t('chat_title')}
        description={t('chat_description')}
      />
      <ChatAssistant caseContext={analysisResult} />
    </div>
  )
}
