"use client"

import { useSyncExternalStore } from "react"

export type DocumentTheme = "dark" | "light"

const THEME_EVENT = "truthseeker-theme-change"

function readTheme(): DocumentTheme {
  if (typeof window === "undefined") {
    return "dark"
  }

  const storedTheme = window.localStorage.getItem("truthseeker-theme")
  if (storedTheme === "dark" || storedTheme === "light") {
    return storedTheme
  }

  return document.documentElement.classList.contains("dark") ? "dark" : "light"
}

function subscribe(onStoreChange: () => void) {
  if (typeof window === "undefined") {
    return () => {}
  }

  const observer = new MutationObserver(() => {
    onStoreChange()
  })

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  })

  window.addEventListener("storage", onStoreChange)
  window.addEventListener(THEME_EVENT, onStoreChange)

  return () => {
    observer.disconnect()
    window.removeEventListener("storage", onStoreChange)
    window.removeEventListener(THEME_EVENT, onStoreChange)
  }
}

export function applyDocumentTheme(theme: DocumentTheme) {
  if (typeof window === "undefined") {
    return
  }

  document.documentElement.classList.toggle("dark", theme === "dark")
  window.localStorage.setItem("truthseeker-theme", theme)
  window.dispatchEvent(new Event(THEME_EVENT))
}

export function useDocumentTheme(): DocumentTheme {
  return useSyncExternalStore(subscribe, readTheme, (): DocumentTheme => "dark")
}
