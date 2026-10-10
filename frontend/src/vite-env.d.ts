/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Hermod API base URL. Defaults to http://localhost:8000. */
  readonly VITE_API_URL?: string
  /** Sent as X-API-Key when the backend has API_KEY set. */
  readonly VITE_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
