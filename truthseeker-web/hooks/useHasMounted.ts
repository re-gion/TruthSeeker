"use client"

import { useSyncExternalStore } from "react"

function subscribe() {
  return () => {}
}

export function useHasMounted() {
  return useSyncExternalStore(subscribe, () => true, () => false)
}
