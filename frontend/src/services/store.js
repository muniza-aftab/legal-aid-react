import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAppStore = create(
  persist(
    (set, get) => ({
      // Language
      language: 'English',
      languageChosen: false,
      setLanguage: (lang) => set({ language: lang }),
      chooseLanguage: (lang) => set({ language: lang, languageChosen: true }),

      // City
      city: '',
      setCity: (city) => set({ city }),

      // App config (from /api/config)
      appConfig: null,
      setAppConfig: (config) => set({ appConfig: config }),

      // Analysis result
      analysisResult: null,
      setAnalysisResult: (result) => set({ analysisResult: result }),
      clearAnalysis: () => set({ analysisResult: null }),

      // Chat session
      chatSessionId: null,
      chatMessages: [],
      setChatSessionId: (id) => set({ chatSessionId: id }),
      setChatMessages: (msgs) => set({ chatMessages: msgs }),
      addChatMessage: (msg) => set(s => ({ chatMessages: [...s.chatMessages, msg] })),
      clearChat: () => set({ chatMessages: [], chatSessionId: null }),

      // Query history (this session)
      queryHistory: [],
      addToHistory: (entry) => set(s => ({
        queryHistory: [entry, ...s.queryHistory].slice(0, 10),
      })),
      clearHistory: () => set({ queryHistory: [] }),

      // Admin
      adminAuthenticated: false,
      adminToken: null,
      setAdminAuth: (token) => set({ adminAuthenticated: true, adminToken: token }),
      clearAdminAuth: () => set({ adminAuthenticated: false, adminToken: null }),

      // UI
      sidebarOpen: false,
      toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),

      // AI Assistant Drawer
      aiDrawerOpen: false,
      toggleAiDrawer: () => set(s => ({ aiDrawerOpen: !s.aiDrawerOpen })),
      openAiDrawer:   () => set({ aiDrawerOpen: true }),
      closeAiDrawer:  () => set({ aiDrawerOpen: false }),

      // Theme
      theme: 'dark',
      toggleTheme: () => set(s => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
    }),
    {
      name: 'legal-aid-store',
      partialize: (state) => ({
        language: state.language,
        city: state.city,
        theme: state.theme,
        adminAuthenticated: state.adminAuthenticated,
        adminToken: state.adminToken,
      }),
    }
  )
)
