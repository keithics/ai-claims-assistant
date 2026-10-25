import { useContext } from "react";
import { ConversationContext, type Conversation } from "./conversation-context";

export function useConversation(): Conversation {
  const value = useContext(ConversationContext);
  if (!value)
    throw new Error("useConversation must be used inside ConversationProvider");
  return value;
}
