"use client"

import { useEffect, useRef } from "react"
import { useTheme } from "next-themes"
import { motion } from "motion/react"
import { Globe as GlobeIcon, Activity, Radar, Crosshair } from "lucide-react"
import createGlobe from "cobe"

export function NetworkGraphUI() {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const { resolvedTheme } = useTheme()
    const isLight = resolvedTheme === "light"

    useEffect(() => {
        let phi = 0
        if (!canvasRef.current) return

        const globe = createGlobe(canvasRef.current, {
            devicePixelRatio: 2,
            width: 2000,
            height: 2000,
            phi: 0,
            theta: 0.2,
            dark: 1,
            diffuse: 2.2,
            mapSamples: 40000,
            mapBrightness: 10,
            baseColor: isLight ? [0.93, 0.95, 1] : [0.15, 0.15, 0.17],     // Dark gray for dark, icy blue-white for light
            markerColor: [0.83, 1, 0.07],   // Cyber Lime #D4FF12
            glowColor: isLight ? [0.6, 0.8, 1] : [0.38, 0.4, 0.94],   // Bright light blue for light, Indigo-AI #6366F1 for dark
            opacity: 0.8,
            markers: [
                // Simulating active threat detection nodes around the world
                { location: [37.7595, -122.4367], size: 0.1 }, // SF
                { location: [40.7128, -74.0060], size: 0.08 }, // NY
                { location: [51.5074, -0.1278], size: 0.06 },  // London
                { location: [35.6895, 139.6917], size: 0.12 }, // Tokyo
                { location: [39.9042, 116.4074], size: 0.15 }, // Beijing
                { location: [-33.8688, 151.2093], size: 0.07 },// Sydney
                { location: [1.3521, 103.8198], size: 0.05 },  // Singapore
                { location: [55.7558, 37.6173], size: 0.09 },  // Moscow
            ],
            onRender: (state) => {
                // Called on every animation frame.
                state.phi = phi
                phi += 0.0025
            },
        })

        return () => {
            globe.destroy()
        }
    }, [isLight]) // Re-run effect map creation whenever the theme changes

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative w-full mt-4 mb-8 flex items-center justify-center"
        >
            {/* Ambient Vignette — only top/bottom fade, not sides */}
            <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-[var(--background)] to-transparent z-10 pointer-events-none" />
            <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[var(--background)] to-transparent z-10 pointer-events-none" />

            {/* Top Left Title Overlay */}
            <div className="absolute top-20 md:top-24 left-6 md:left-8 z-20 pointer-events-none">
                <div className="flex items-center gap-3 bg-black/40 backdrop-blur-md px-5 py-2.5 rounded-2xl border border-white/10 shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
                    <GlobeIcon className="w-5 h-5 text-[#D4FF12] animate-pulse" />
                    <div className="flex flex-col">
                        <span className="text-white font-medium text-sm">全球溯源拓扑图 (Global Threat OSINT)</span>
                        <span className="text-[#6366F1] font-mono text-xs font-bold tracking-widest uppercase">● Analyzing Earth Nodes</span>
                    </div>
                </div>
            </div>

            {/* Bottom Left Metrics Overlay */}
            <div className="absolute bottom-6 left-6 md:left-8 md:bottom-12 z-20 pointer-events-none flex flex-col gap-3">
                <div className="bg-black/40 shadow-xl backdrop-blur-xl px-4 py-3 rounded-2xl border border-white/10 flex items-center gap-4">
                    <div className="p-2 bg-[#EF4444]/20 rounded-lg">
                        <Radar className="w-5 h-5 text-[#EF4444] animate-pulse" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-xs text-white/50 uppercase tracking-widest">Malicious Nodes</span>
                        <span className="text-white font-mono text-lg font-bold">142</span>
                    </div>
                </div>
                <div className="bg-black/40 shadow-xl backdrop-blur-xl px-4 py-3 rounded-2xl border border-white/10 flex items-center gap-4">
                    <div className="p-2 bg-[#6366F1]/20 rounded-lg">
                        <Activity className="w-5 h-5 text-[#6366F1]" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-xs text-white/50 uppercase tracking-widest">Forensic Agents</span>
                        <span className="text-white font-mono text-lg font-bold">28</span>
                    </div>
                </div>
                <div className="bg-black/40 shadow-xl backdrop-blur-xl px-4 py-3 rounded-2xl border border-white/10 flex items-center gap-4">
                    <div className="p-2 bg-[#D4FF12]/20 rounded-lg">
                        <Crosshair className="w-5 h-5 text-[#D4FF12]" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-xs text-white/50 uppercase tracking-widest">Intercept Events</span>
                        <span className="text-white font-mono text-lg font-bold">81/sec</span>
                    </div>
                </div>
            </div>

            {/* The 3D Globe Canvas Container — 使用 mx-auto 确保球心在页面中间竖线 */}
            <div className="w-[90vw] md:w-[80vw] lg:w-[75vw] max-w-[900px] aspect-square mx-auto flex items-center justify-center z-0 pointer-events-none">
                <canvas
                    ref={canvasRef}
                    style={{
                        width: "100%",
                        height: "100%",
                        opacity: 1,
                    }}
                    className={`object-contain origin-center pointer-events-auto outline-none select-none transition-all duration-700 ${isLight
                            ? "drop-shadow-[0_0_100px_rgba(150,200,255,0.4)]"
                            : "drop-shadow-[0_0_100px_rgba(99,102,241,0.3)]"
                        }`}
                />
            </div>
        </motion.div>
    )
}
