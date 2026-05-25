import "./i18n";
import { initLogBuffer } from "./utils/logBuffer";
import { initDebugFromBackend } from "./utils/debug";
import { StrictMode } from "react";

// Install console interceptors ASAP so all logs are captured
initLogBuffer();
// Sync frontend debug flag from backend log level
initDebugFromBackend();
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 seconds
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

ReactDOM.createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
