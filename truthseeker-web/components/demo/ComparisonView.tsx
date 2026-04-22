"use client"

import { useState, useRef, useEffect } from "react"
import { ScanFace, AlertTriangle, ShieldCheck } from "lucide-react"

export function ComparisonView() {
    const [sliderPosition, setSliderPosition] = useState(50)
    const containerRef = useRef<HTMLDivElement>(null)
    const [isDragging, setIsDragging] = useState(false)

    const handleMove = (clientX: number) => {
        if (!containerRef.current) return
        const rect = containerRef.current.getBoundingClientRect()
        const x = Math.max(0, Math.min(clientX - rect.left, rect.width))
        const percent = Math.max(0, Math.min((x / rect.width) * 100, 100))
        setSliderPosition(percent)
    }

    const handlePointerDown = () => setIsDragging(true)
    const handlePointerUp = () => setIsDragging(false)

    useEffect(() => {
        const handlePointerMove = (e: PointerEvent) => {
            if (!isDragging) return
            handleMove(e.clientX)
        }

        if (isDragging) {
            window.addEventListener('pointermove', handlePointerMove)
            window.addEventListener('pointerup', handlePointerUp)
        }

        return () => {
            window.removeEventListener('pointermove', handlePointerMove)
            window.removeEventListener('pointerup', handlePointerUp)
        }
    }, [isDragging])

    return (
        <div className="w-full max-w-4xl mx-auto my-8">
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <ScanFace className="text-[#6366F1] w-6 h-6" />
                        真假特征对比视图
                    </h3>
                    <p className="text-sm text-[#C0C0C0] mt-1">拖动滑块直观对比原始素材与伪造素材的像素级差异</p>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono">
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                        <span className="text-[#C0C0C0]">原始 (Authentic)</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#EF4444]" />
                        <span className="text-[#C0C0C0]">伪造 (Forged)</span>
                    </div>
                </div>
            </div>

            <div
                ref={containerRef}
                className="relative w-full aspect-video rounded-2xl overflow-hidden cursor-ew-resize select-none bg-black border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
                onPointerDown={handlePointerDown}
            >
                {/* Authentic Image (Background) */}
                <div className="absolute inset-0 w-full h-full bg-[#1A1A1A] flex items-center justify-center">
                    {/* Mock content for authentic */}
                    <div className="text-center absolute">
                        <ShieldCheck className="w-16 h-16 text-[#10B981]/20 mx-auto mb-4" />
                        <span className="text-white/30 font-mono tracking-widest">ORIGINAL SOURCE</span>

                        {/* Simulated subtle natural noise */}
                        <div className="absolute inset-0 mix-blend-overlay opacity-30" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noiseFilter\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noiseFilter)\'/%3E%3C/svg%3E")' }}></div>
                    </div>

                    <div className="absolute inset-0 opacity-80 bg-gradient-to-br from-[#1a2a3a] via-[#2a3a4a] to-[#1a2a3a]" />
                </div>

                {/* Forged Image (Foreground, clipped) */}
                <div
                    className="absolute top-0 left-0 bottom-0 h-full bg-[#2A1A1A] flex items-center justify-center overflow-hidden"
                    style={{ width: `${sliderPosition}%` }}
                >
                    {/* Mock content for forged */}
                    <div className="absolute inset-0 z-10 flex items-center justify-center text-center">
                        <AlertTriangle className="w-16 h-16 text-[#EF4444]/20 mx-auto mb-4" />
                        <span className="text-[#EF4444]/30 font-mono tracking-widest">SYNTHETIC ARTIFACTS</span>
                    </div>

                    <div className="absolute inset-0 opacity-80 bg-gradient-to-br from-[#3a2a1a] via-[#4a3a2a] to-[#3a2a1a] mix-blend-lighten" />

                    {/* Artificial artifacts overlays */}
                    <div className="absolute inset-0 border-[3px] border-[#EF4444]/0">
                        {/* Mock blending boundary artifact */}
                        <div className="absolute top-[30%] left-[40%] w-32 h-48 border border-[#EF4444]/50 rounded-full bg-[#EF4444]/10 blur-[2px]" />
                        <span className="absolute top-[30%] left-[40%] -translate-y-full text-[10px] text-[#EF4444] font-mono bg-black/50 px-1 py-0.5 rounded">
                            BLEND_BOUNDARY_DETECTED
                        </span>
                    </div>
                </div>

                {/* Slider Handle */}
                <div
                    className="absolute top-0 bottom-0 w-1 bg-white cursor-ew-resize flex items-center justify-center z-20 shadow-[0_0_10px_rgba(255,255,255,0.8)]"
                    style={{ left: `calc(${sliderPosition}% - 2px)` }}
                >
                    {/* Handle icon */}
                    <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-lg transform -translate-x-[14px]">
                        <div className="flex gap-1">
                            <span className="w-0.5 h-3 bg-gray-400 rounded-full" />
                            <span className="w-0.5 h-3 bg-gray-400 rounded-full" />
                        </div>
                    </div>
                </div>
            </div>

            {/* Legend & Metrics */}
            <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-[#10B981]/10 border border-[#10B981]/20">
                    <h4 className="text-[#10B981] text-sm font-bold mb-2">原始特征</h4>
                    <ul className="text-xs text-[#C0C0C0] space-y-1">
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#10B981] rounded-full" /> 像素噪声分布均匀均匀</li>
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#10B981] rounded-full" /> 光影反射符合物理规律</li>
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#10B981] rounded-full" /> 边缘平滑无明显拼接缝隙</li>
                    </ul>
                </div>
                <div className="p-4 rounded-xl bg-[#EF4444]/10 border border-[#EF4444]/20">
                    <h4 className="text-[#EF4444] text-sm font-bold mb-2">检出伪造伪影</h4>
                    <ul className="text-xs text-[#C0C0C0] space-y-1">
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#EF4444] rounded-full" /> 脸部轮廓处检测到高频重影 (98.2%)</li>
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#EF4444] rounded-full" /> 肤色饱和度异常跳变</li>
                        <li className="flex items-center gap-2"><span className="w-1 h-1 bg-[#EF4444] rounded-full" /> 牙齿/眼白区域细节丢失</li>
                    </ul>
                </div>
            </div>
        </div>
    )
}
