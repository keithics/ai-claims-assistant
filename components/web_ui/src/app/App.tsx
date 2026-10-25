import { Route, Routes } from "react-router-dom";
import { ApprovalPage } from "../features/approval/ApprovalPage";
import { ChatPage } from "../features/chat/ChatPage";
import { DocumentPage } from "../features/chat/DocumentPage";
import { I18nProvider } from "../i18n/I18nProvider";
import { useConversation } from "../state/useConversation";
import { Layout } from "./Layout";

export function App() {
  const { language } = useConversation();
  return (
    <I18nProvider language={language}>
      <div lang={language} className="root">
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<ChatPage />} />
            <Route path="approvals" element={<ApprovalPage />} />
            <Route path="documents/:docId" element={<DocumentPage />} />
          </Route>
        </Routes>
      </div>
    </I18nProvider>
  );
}
