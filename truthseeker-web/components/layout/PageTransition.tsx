"use client"

import { motion } from "motion/react"
import { usePathname } from "next/navigation"
import { BrandLogo } from "@/components/logo/BrandLogo"

export function PageTransition({ children }: { children: React.ReactNode }) {
    const pathname = usePathname()

    // 每次 pathname 改变时 key 会改变，因此 motion.div 会重新挂载
    // 重新挂载时，overlay 会初始化为不透明 (opacity: 1)，从而立即挡住突然切换的新界面
    // 随后 overlay 滑动并淡出，实现自然真实的转场效果。
    return (
        <motion.div key={pathname} className="w-full h-full relative">
            {/* The Overlay that appears instantly on route change, then animates out */}
            <motion.div
                className="fixed inset-0 z-[99999] flex flex-col items-center justify-center bg-white dark:bg-[#000000] pointer-events-none"
                initial={{ opacity: 1, clipPath: 'inset(0 0 0% 0)' }}
                animate={{ opacity: 0, clipPath: 'inset(100% 0 0 0)' }}
                transition={{ duration: 2, ease: [0.76, 0, 0.24, 1], delay: 0.35 }}
            >
                {/* Background Details */}
                <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-soft-light" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(29,78,216,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(29,78,216,0.03)_1px,transparent_1px)] bg-[size:40px_40px]" />
                
                <div className="flex flex-col items-center gap-6 z-10 w-full px-4 mb-20">
                    <motion.div
                        className="flex flex-col items-center"
                        initial={{ scale: 0.96, opacity: 0, y: 15 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                    >
                        <BrandLogo
                            variant="transition-light"
                            className="block w-[min(80vw,680px)] dark:hidden"
                            imageClassName="h-auto max-h-[68vh] w-full object-contain"
                            size={680}
                            priority
                        />
                        <BrandLogo
                            variant="transition-dark"
                            className="hidden w-[min(80vw,680px)] dark:block"
                            imageClassName="h-auto max-h-[68vh] w-full object-contain"
                            size={680}
                            priority
                        />
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
                                transition={{ duration: 2, ease: "easeInOut" }}
                            />
                        </div>
                    </motion.div>
                </div>
            </motion.div>

            {/* The actual page content */}
            <motion.div 
                initial={{ opacity: 0, scale: 0.98, filter: "blur(4px)" }}
                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                transition={{ duration: 2, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
                className="w-full h-full"
            >
                {children}
            </motion.div>
        </motion.div>
    )
}
