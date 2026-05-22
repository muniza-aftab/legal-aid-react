import { useAppStore } from '@/services/store'
import { useT } from '@/services/i18n'
import { SectionHeader } from '@/components/ui/index'
import ChatAssistant from '@/components/chat/ChatAssistant'
import { PageContainer } from '@/components/layout/PageLayout'

export default function ChatPage() {
  const t = useT()
  const { language, analysisResult } = useAppStore()

  return (
    <PageContainer size="standard">
      <SectionHeader
        eyebrow={t('chat_eyebrow')}
        title={t('chat_title')}
        description={t('chat_description')}
      />
      <ChatAssistant caseContext={analysisResult} />
    </PageContainer>
  )
}
