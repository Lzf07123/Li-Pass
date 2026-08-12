import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { DOCUMENT_TITLE, FAVICON_WEBP } from './lib/brand'
import { ToastProvider } from './components/ToastProvider'
import { initRipple } from './lib/ripple'

/**
 * 品牌变量化：标题与 favicon 从 brand.ts 读取，替换配置即全局生效。
 * 图标统一使用 WebP 单格式，浏览器直接加载。
 */
function applyBrandAssets() {
  document.title = DOCUMENT_TITLE

  const head = document.head
  head
    .querySelectorAll<HTMLLinkElement>(
      'link[rel="icon"], link[rel="apple-touch-icon"]',
    )
    .forEach((link) => link.remove())

  const link = document.createElement('link')
  link.rel = 'icon'
  link.type = 'image/webp'
  link.href = FAVICON_WEBP
  head.appendChild(link)
}

applyBrandAssets()
initRipple()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
