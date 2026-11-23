import { useState, useEffect, useCallback } from 'react'
import { Idea } from '../../tools/types'
import { api } from '../../tools/api'
import IdeaList from '../../components/IdeaList/IdeaList'
import StepWizard from '../../components/StepWizard/StepWizard'
import Hans4Workspace from '../../components/Hans4Workspace/Hans4Workspace'
import ApiKeyModal from '../../components/ApiKeyModal/ApiKeyModal'
import {
  AppLayout, Header, HeaderLogo, LogoDot, HeaderTitle,
  Layout, Sidebar, Main, EmptyState, EmptyIcon, ApiKeyBtn, ApiKeyDot,
} from './MainView.styled'

export default function MainView() {
  const [ideas, setIdeas] = useState<Idea[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768)
  const [showApiKey, setShowApiKey] = useState(false)
  const [hans4Open, setHans4Open] = useState(false)
  const [keyConfigured, setKeyConfigured] = useState<boolean | null>(null)

  const fetchIdeas = useCallback(async () => {
    try {
      const data = await api.ideas.list()
      setIdeas(data)
    } catch { /* server not ready */ }
  }, [])

  const handleCreated = useCallback((idea: Idea) => {
    setIdeas(prev => [...prev, idea])
    setSelectedId(idea.id)
    setHans4Open(false)
  }, [])

  const checkKey = useCallback(async () => {
    try {
      const d = await api.geminiKey.check()
      setKeyConfigured(d.configured)
    } catch { setKeyConfigured(false) }
  }, [])

  useEffect(() => { fetchIdeas(); checkKey() }, [fetchIdeas, checkKey])

  useEffect(() => {
    const handler = () => { if (window.innerWidth < 768) setSidebarOpen(false) }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  const selectedIdea = ideas.find(i => i.id === selectedId) ?? null

  return (
    <AppLayout>
      <Header>
        <HeaderLogo>
          <LogoDot />
          <HeaderTitle>Content Engine</HeaderTitle>
        </HeaderLogo>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {selectedId !== null && (
            <ApiKeyBtn type="button" onClick={() => setHans4Open(v => !v)} title="Open the local Hans4 character bible and image handoff">
              {hans4Open ? 'Back to idea' : 'Hans4 Studio'}
            </ApiKeyBtn>
          )}
        <ApiKeyBtn
          onClick={() => setShowApiKey(true)}
          title={keyConfigured ? 'Gemini API key configured' : 'Configure Gemini API key'}
        >
          <ApiKeyDot $ok={keyConfigured === true} />
          Gemini Key
        </ApiKeyBtn>
        </div>
      </Header>

      <Layout>
        <Sidebar $open={sidebarOpen}>
          <IdeaList
            ideas={ideas}
            selectedId={selectedId}
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen(o => !o)}
            onSelect={id => { setSelectedId(id); setHans4Open(false) }}
            onCreated={handleCreated}
          />
        </Sidebar>
        <Main>
          {selectedIdea ? (
            hans4Open ? <Hans4Workspace ideaId={selectedIdea.id} onClose={() => setHans4Open(false)} /> :
            <StepWizard idea={selectedIdea} onUpdate={fetchIdeas} />
          ) : (
            <EmptyState>
              <EmptyIcon>✦</EmptyIcon>
              <p>Select an idea or create a new one</p>
            </EmptyState>
          )}
        </Main>
      </Layout>

      {showApiKey && (
        <ApiKeyModal onClose={() => { setShowApiKey(false); checkKey() }} />
      )}
    </AppLayout>
  )
}
