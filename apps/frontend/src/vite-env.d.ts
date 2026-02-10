/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  // Add more env variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
