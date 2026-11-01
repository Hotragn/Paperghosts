import * as Sentry from '@sentry/react'

// Sentry for the Morgue: browser tracing (which records Web Vitals) and error capture, sent to
// paperghosts-web. It starts only when the build is given VITE_SENTRY_DSN, so the code holds no
// DSN; the release is the commit the build came from. Nothing about the reader is sent.
export function startSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
  if (!dsn) return
  Sentry.init({
    dsn,
    release: import.meta.env.VITE_SENTRY_RELEASE as string | undefined,
    environment: import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 1.0,
    // nothing about the reader: no user, cookies, headers, bodies or query strings
    dataCollection: { userInfo: false, cookies: false, httpHeaders: false, httpBodies: [], urlQueryParams: false },
  })
}
