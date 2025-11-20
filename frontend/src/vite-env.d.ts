/// <reference types="vite/client" />

declare module 'mermaid' {
  const mermaid: any
  export default mermaid
}

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
