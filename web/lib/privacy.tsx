"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";

const LS_KEY = "hide_numbers";

interface PrivacyContextValue {
  hidden: boolean;
  toggle: () => void;
  mask: (value: string) => string;
}

const PrivacyContext = createContext<PrivacyContextValue>({
  hidden: false,
  toggle: () => {},
  mask: (v) => v,
});

export function PrivacyProvider({ children }: { children: React.ReactNode }) {
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setHidden(localStorage.getItem(LS_KEY) === "1");
  }, []);

  const toggle = useCallback(() => {
    setHidden((prev) => {
      const next = !prev;
      localStorage.setItem(LS_KEY, next ? "1" : "0");
      return next;
    });
  }, []);

  const mask = useCallback(
    (value: string) => (hidden ? "••••••" : value),
    [hidden]
  );

  return (
    <PrivacyContext.Provider value={{ hidden, toggle, mask }}>
      {children}
    </PrivacyContext.Provider>
  );
}

export function usePrivacy() {
  return useContext(PrivacyContext);
}
