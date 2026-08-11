import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    /*
      Two environments, chosen per file rather than globally.

      Most tests here are pure functions — packet decoding, formatting, device
      recognition — and those run far faster without a simulated DOM. The hooks
      that hold the sensor connection and the session state genuinely need one,
      because their whole behaviour lives in effects and state transitions that
      cannot happen outside React's renderer. Those files opt in with a
      `@vitest-environment jsdom` comment at the top.
    */
    environment: 'node',
  },
})
