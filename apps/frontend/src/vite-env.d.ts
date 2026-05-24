/// <reference types="vite/client" />

declare const __TUNEIN_SUPPORTED__: boolean;

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  // Add more env variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
