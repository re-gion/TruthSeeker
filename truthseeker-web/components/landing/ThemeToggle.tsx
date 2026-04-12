"use client"

import { useEffect, useState } from "react"
import { motion } from "motion/react"

export function ThemeToggle() {
    const [theme, setTheme] = useState<"dark" | "light">("dark")
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
        const storedTheme = localStorage.getItem("truthseeker-theme") as "dark" | "light"
        if (storedTheme) {
            setTheme(storedTheme)
            if (storedTheme === "light") {
                document.documentElement.classList.remove("dark")
            } else {
                document.documentElement.classList.add("dark")
            }
        }
    }, [])

    const toggleTheme = () => {
        const newTheme = theme === "dark" ? "light" : "dark"
        setTheme(newTheme)
        localStorage.setItem("truthseeker-theme", newTheme)

        if (newTheme === "dark") {
            document.documentElement.classList.add("dark")
        } else {
            document.documentElement.classList.remove("dark")
        }
    }

    if (!mounted) {
        return <div className="w-10 h-10 rounded-full bg-muted animate-pulse" />
    }

    return (
        <motion.button
            onClick={toggleTheme}
            className="relative flex items-center justify-center w-10 h-10 rounded-full bg-muted hover:bg-accent border border-border backdrop-blur-md transition-colors overflow-hidden group"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            aria-label="Toggle theme"
        >
            <motion.div
                initial={false}
                animate={{
                    y: theme === "dark" ? 0 : -40,
                    opacity: theme === "dark" ? 1 : 0
                }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                className="absolute inset-0 flex items-center justify-center text-[#D4FF12]"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
                </svg>
            </motion.div>
            <motion.div
                initial={false}
                animate={{
                    y: theme === "light" ? 0 : 40,
                    opacity: theme === "light" ? 1 : 0
                }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                className="absolute inset-0 flex items-center justify-center text-[#6366F1]"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v2" />
                    <path d="M12 20v2" />
                    <path d="m4.93 4.93 1.41 1.41" />
                    <path d="m17.66 17.66 1.41 1.41" />
                    <path d="M2 12h2" />
                    <path d="M20 12h2" />
                    <path d="m6.34 17.66-1.41 1.41" />
                    <path d="m19.07 4.93-1.41 1.41" />
                </svg>
            </motion.div>
        </motion.button>
    )
}
