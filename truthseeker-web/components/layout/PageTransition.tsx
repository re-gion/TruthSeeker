"use client"

import { motion } from "motion/react"
import { usePathname } from "next/navigation"

export function PageTransition({ children }: { children: React.ReactNode }) {
    const pathname = usePathname()

    // 每次 pathname 改变时 key 会改变，因此 motion.div 会重新挂载
    // 重新挂载时，overlay 会初始化为不透明 (opacity: 1)，从而立即挡住突然切换的新界面
    // 随后 overlay 滑动并淡出，实现自然真实的转场效果。
    return (
        <motion.div key={pathname} className="w-full h-full relative">
            {/* The Overlay that appears instantly on route change, then animates out */}
            <motion.div
                className="fixed inset-0 z-[99999] flex flex-col items-center justify-center bg-white dark:bg-[#0A0A0F] pointer-events-none"
                initial={{ opacity: 1, clipPath: 'inset(0 0 0% 0)' }}
                animate={{ opacity: 0, clipPath: 'inset(100% 0 0 0)' }}
                transition={{ duration: 0.9, ease: [0.76, 0, 0.24, 1], delay: 0.35 }}
            >
                {/* Background Details */}
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-soft-light" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(29,78,216,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(29,78,216,0.03)_1px,transparent_1px)] bg-[size:40px_40px]" />
                
                <div className="flex flex-col items-center gap-6 z-10 w-full px-4 mb-20">
                    <motion.div
                        className="flex flex-col items-center"
                        initial={{ scale: 0.9, opacity: 0, y: 15 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                    >
                        {/* Custom Blue ST Logo based on user's image */}
                        <svg width="120" height="120" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="drop-shadow-xl">
                            {/* The "S" curve */}
                            <path d="M 45 25 C 10 30 15 70 45 80" stroke="#001CE8" strokeWidth="8" strokeLinecap="round" />
                            {/* The dot */}
                            <circle cx="48" cy="18" r="6" fill="#001CE8" />
                            {/* The "T" cap and stem */}
                            <path d="M 40 38 L 85 38" stroke="#001CE8" strokeWidth="8" strokeLinecap="round" />
                            <path d="M 60 38 L 65 75" stroke="#001CE8" strokeWidth="8" strokeLinecap="round" />
                            {/* The right arc */}
                            <path d="M 65 80 C 85 75 90 55 85 45" stroke="#001CE8" strokeWidth="8" strokeLinecap="round" />
                        </svg>
                        
                        <h1 className="text-5xl md:text-6xl font-black mt-3 tracking-tight text-[#001CE8]">
                            TruthSeeker
                        </h1>
                    </motion.div>

                    {/* Loader */}
                    <motion.div 
                        className="flex flex-col items-center gap-3 mt-4"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.2 }}
                    >
                        <motion.span 
                            className="text-[#001CE8] font-mono text-sm tracking-[0.3em] font-bold"
                            animate={{ opacity: [1, 0.4, 1] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                        >
                            VERIFYING TRUTH...
                        </motion.span>
                        {/* Progress Bar */}
                        <div className="w-48 h-[3px] bg-[#001CE8]/20 rounded-full overflow-hidden relative">
                            <motion.div 
                                className="absolute inset-y-0 left-0 bg-[#001CE8]"
                                initial={{ width: "0%" }}
                                animate={{ width: "100%" }}
                                transition={{ duration: 1.0, ease: "easeInOut" }}
                            />
                        </div>
                    </motion.div>
                </div>
            </motion.div>

            {/* The actual page content */}
            <motion.div 
                initial={{ opacity: 0, scale: 0.98, filter: "blur(4px)" }}
                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
                className="w-full h-full"
            >
                {children}
            </motion.div>
        </motion.div>
    )
}
