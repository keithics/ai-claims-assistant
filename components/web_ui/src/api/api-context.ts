import { createContext } from "react";
import type { Api } from "./client";

export const ApiContext = createContext<Api | null>(null);
