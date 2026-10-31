import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/unifrakturmaguntia/400.css'
import '@fontsource/bodoni-moda/400.css'
import '@fontsource/bodoni-moda/700.css'
import '@fontsource/newsreader/400.css'
import '@fontsource/newsreader/400-italic.css'
import '@fontsource/newsreader/600.css'
import '@fontsource/courier-prime/400.css'
import '@fontsource/courier-prime/700.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
