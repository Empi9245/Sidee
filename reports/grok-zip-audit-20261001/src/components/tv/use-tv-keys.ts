import { useEffect, useRef } from "react";

export function useTvKeys(handlers: {
  onBlue?: () => void;
  onBack?: () => void;
  onRed?: () => void;
}) {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const code = event.keyCode || event.which;
      if (code === 406 || event.key === "F9") {
        event.preventDefault();
        ref.current.onBlue?.();
        return;
      }
      if (code === 403) {
        event.preventDefault();
        ref.current.onRed?.();
        return;
      }
      if (event.key === "Escape" || event.key === "Backspace" || code === 8 || code === 461) {
        const tag = (event.target as HTMLElement | null)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        event.preventDefault();
        ref.current.onBack?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
