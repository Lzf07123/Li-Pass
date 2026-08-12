import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { DOCUMENT_TITLE, FAVICON_PATH } from './lib/brand'
import { ToastProvider } from './components/ToastProvider'

// 品牌变量化：标题与 favicon 从配置读取，替换 brand.ts 即全局生效
document.title = DOCUMENT_TITLE
const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
if (favicon) favicon.href = FAVICON_PATH

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
