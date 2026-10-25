import { useContext } from "react";
import type { Api } from "./client";
import { ApiContext } from "./api-context";

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api)
    throw new Error("useApi must be used inside an ApiContext provider");
  return api;
}
