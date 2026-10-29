import { createContext, useCallback, useContext, useState } from "react";

const ToastContext = createContext({ success: () => {}, error: () => {} });

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((kind, message) => {
    const id = Math.random().toString(36).slice(2);
    setItems((s) => [...s, { id, kind, message }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 5000);
  }, []);
  const api = { success: (m) => push("success", m), error: (m) => push("error", m) };
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (
          <p key={t.id} className={`panel p-3 text-sm shadow-lg ${t.kind === "success" ? "border-check-500 text-check-700" : "border-mark-500 text-mark-700"}`}>{t.message}</p>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
