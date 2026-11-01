import { execSync } from 'node:child_process'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// the release is the commit: the host's own (Render sets RENDER_GIT_COMMIT) or the checkout's
const release =
  process.env.RENDER_GIT_COMMIT ??
  (() => {
    try {
      return execSync('git rev-parse HEAD').toString().trim()
    } catch {
      return undefined
    }
  })()
process.env.VITE_SENTRY_RELEASE ??= release

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // source maps go to Sentry for this release only when the build has SENTRY_AUTH_TOKEN, and
    // are deleted from the build afterwards, so the site never serves them
    ...(process.env.SENTRY_AUTH_TOKEN
      ? [
          sentryVitePlugin({
            org: 'hotragn',
            project: 'paperghosts-web',
            authToken: process.env.SENTRY_AUTH_TOKEN,
            release: { name: release },
            sourcemaps: { filesToDeleteAfterUpload: ['./dist/**/*.map'] },
            telemetry: false,
          }),
        ]
      : []),
  ],
  // relative paths, so the static build opens from any folder or host
  base: './',
  build: { sourcemap: process.env.SENTRY_AUTH_TOKEN ? 'hidden' : false },
})
