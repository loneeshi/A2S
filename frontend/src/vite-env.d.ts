/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly imports: ImportMetaEnv
  readonly env: ImportMetaEnv
  readonly modules: string
  readonly build: string
}

interface ImportMetaEnv {
  readonly VITE_APP_TITLE: string
  readonly BASE_URL: string
}
