"use client"

import { useState, useEffect } from "react"

export function useScrollProgress() {
    const [progress, setProgress] = useState(0)

    useEffect(() => {
        const updateScroll = () => {
            const currentScrollY = window.scrollY
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight
            if (scrollHeight > 0) {
                setProgress(Number((currentScrollY / scrollHeight).toFixed(4)))
            } else {
                setProgress(0)
            }
        }

        // initial call
        updateScroll()

        window.addEventListener("scroll", updateScroll, { passive: true })
        return () => window.removeEventListener("scroll", updateScroll)
    }, [])

    return progress
}
