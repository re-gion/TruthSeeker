"use client"

import { useState, useEffect } from 'react'

export function useCountUp(end: number, duration: number = 2000, startWhen: boolean = true) {
    const [count, setCount] = useState(0)

    useEffect(() => {
        if (!startWhen) return

        let startTime: number | null = null
        let animationFrame: number

        const updateCount = (timestamp: number) => {
            if (!startTime) startTime = timestamp
            const progress = timestamp - startTime

            // calculate the current value based on progress and easing (ease-out-expo)
            const p = Math.min(progress / duration, 1)
            const easeOutExpo = p === 1 ? 1 : 1 - Math.pow(2, -10 * p)

            const currentCount = Math.floor(easeOutExpo * end)

            if (currentCount <= end) {
                setCount(currentCount)
            }

            if (progress < duration) {
                animationFrame = requestAnimationFrame(updateCount)
            } else {
                setCount(end)
            }
        }

        animationFrame = requestAnimationFrame(updateCount)

        return () => cancelAnimationFrame(animationFrame)
    }, [end, duration, startWhen])

    return count
}
