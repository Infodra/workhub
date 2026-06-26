"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const initial = localStorage.getItem("workhub-theme") === "dark";
    setDark(initial);
    document.documentElement.classList.toggle("dark", initial);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("workhub-theme", next ? "dark" : "light");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-full border px-4 py-2 text-sm font-semibold"
      aria-label="Toggle theme"
    >
      {dark ? "Light" : "Dark"} Mode
    </button>
  );
}
