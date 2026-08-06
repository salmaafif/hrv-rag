import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// The non-null assertion is safe: index.html always contains <div id="root">.
// It is the one place in the app where we override the compiler rather than
// handle a null, and it is here because the alternative — crashing later with a
// less obvious message — is worse.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
