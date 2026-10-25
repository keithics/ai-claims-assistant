import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { createApi } from "./api/client";
import { ApiContext } from "./api/api-context";
import { loadConfig } from "./api/config";
import { App } from "./app/App";
import { ConversationProvider } from "./state/ConversationProvider";
import "./styles.css";

async function start() {
  const config = await loadConfig();
  const api = createApi(config.apiBaseUrl);
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ApiContext.Provider value={api}>
        <BrowserRouter>
          <ConversationProvider>
            <App />
          </ConversationProvider>
        </BrowserRouter>
      </ApiContext.Provider>
    </StrictMode>,
  );
}

void start();
