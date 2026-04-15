"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import { motion, AnimatePresence } from "motion/react"
import { createClient } from "@/lib/supabase/client"

const ACCEPTED_TYPES = ["video/mp4", "video/webm", "audio/mpeg", "audio/wav", "image/jpeg", "image/png", "image/webp", "text/plain"]
const ACCEPTED_EXT = ".mp4,.webm,.mp3,.wav,.jpg,.jpeg,.png,.webp,.txt"
const promptTemplates = [
    "请判断该内容是否存在 AI 伪造、拼接或篡改痕迹，并给出关键依据。",
    "请从画面/音频/文本一致性、来源可信度和传播风险三个角度展开分析。",
    "请优先识别是否涉及诈骗、舆情操纵或深度伪造传播链，并输出处置建议。"
]
const aspectOptions = ["多模态取证优先", "跨模态一致性", "传播链溯源", "高风险案件"]

const focusMapping: Record<string, "balanced" | "visual" | "audio" | "text"> = {
    "多模态取证优先": "balanced",
    "跨模态一致性": "visual",
    "传播链溯源": "text",
    "高风险案件": "balanced",
}

function getInputType(file: File | null, textPrompt: string): string {
    if (file?.type.startsWith("video/")) return "video"
    if (file?.type.startsWith("audio/")) return "audio"
    if (file?.type.startsWith("image/")) return "image"
    // F-5 修复：无文件时默认 text 而非 image
    return textPrompt.trim() ? "text" : "text"
}

function formatSize(bytes: number): string {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** F-1 修复：从 Supabase session 获取 access_token */
async function getAuthToken(): Promise<string | null> {
    try {
        const supabase = createClient()
        const { data } = await supabase.auth.getSession()
        return data.session?.access_token ?? null
    } catch {
        return null
    }
}

export function FileUploader() {
    const router = useRouter()
    const [isDragging, setIsDragging] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [progress, setProgress] = useState(0)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [textPrompt, setTextPrompt] = useState("")
    const [shareToCasebase, setShareToCasebase] = useState(false)
    const [selectedFocus, setSelectedFocus] = useState("多模态取证优先")

    const launchAnalysis = useCallback(async (file: File | null, prompt: string) => {
        setError(null)
        if (!file && !prompt.trim()) {
            setError("请上传多媒体内容或填写文本说明")
            return
        }
        if (file) {
            if (!ACCEPTED_TYPES.includes(file.type)) {
                setError(`不支持的文件类型：${file.type}`)
                return
            }
            if (file.size > 500 * 1024 * 1024) {
                setError("文件大小不能超过 500MB")
                return
            }
        }
        setUploading(true)
        setProgress(0)
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

        try {
            let fileUrl: string | null = null
            const inputType = getInputType(file, prompt)
            const authToken = await getAuthToken()
            const priorityFocus = focusMapping[selectedFocus] || "balanced"

            // Step 1: 上传文件（如果有）
            if (file) {
                setProgress(10)
                const formData = new FormData()
                formData.append("file", file)
                // F-1 修复：携带认证 token
                const uploadHeaders: Record<string, string> = {}
                if (authToken) uploadHeaders["Authorization"] = `Bearer ${authToken}`

                const uploadResp = await fetch(`${apiBase}/api/v1/upload/`, {
                    method: "POST",
                    body: formData,
                    headers: uploadHeaders,
                })
                if (!uploadResp.ok) {
                    const err = await uploadResp.json().catch(() => ({}))
                    throw new Error(err.detail || "文件上传失败")
                }
                const uploadData = await uploadResp.json()
                fileUrl = uploadData.file_url
                setProgress(50)
            }

            // Step 2: 创建任务
            const title = file?.name || prompt.slice(0, 18) || "文本分析任务"
            const taskHeaders: Record<string, string> = { "Content-Type": "application/json" }
            if (authToken) taskHeaders["Authorization"] = `Bearer ${authToken}`

            const resp = await fetch(`${apiBase}/api/v1/tasks`, {
                method: "POST",
                headers: taskHeaders,
                body: JSON.stringify({
                    title,
                    input_type: inputType,
                    description: prompt.trim() || `上传文件: ${file?.name}`,
                    priority_focus: priorityFocus,
                    metadata: {
                        share_to_casebase: shareToCasebase,
                        analysis_focus: selectedFocus,
                        has_file: Boolean(file),
                    },
                }),
            })

            // F-3 修复：任务创建失败时显示错误而非静默降级
            if (!resp.ok) {
                const errBody = await resp.json().catch(() => ({}))
                throw new Error(errBody.detail || "任务创建失败，请重试")
            }
            const taskData = await resp.json()
            const taskId = taskData.id
            setProgress(100)
            await new Promise((r) => setTimeout(r, 350))

            const query = new URLSearchParams({ type: inputType })
            if (fileUrl) query.set("url", fileUrl)
            else query.set("url", "mock://text-input")
            if (prompt.trim()) query.set("prompt", prompt.trim())
            query.set("focus", priorityFocus)

            router.push(`/detect/${taskId}?${query.toString()}`)
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "上传失败，请重试"
            setError(msg)
            setUploading(false)
            setProgress(0)
        }
    }, [router, selectedFocus, shareToCasebase])

    const handleFile = useCallback((file: File) => {
        setSelectedFile(file)
        setError(null)
    }, [])

    const onDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
    }, [handleFile])

    const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
    }

    return (
        <div className="w-full max-w-5xl mx-auto">
            <div className="relative overflow-hidden rounded-[2rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(245,243,239,0.98)_100%)] shadow-[0_30px_90px_rgba(15,23,42,0.10)] backdrop-blur-xl dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(30,30,34,0.94)_0%,rgba(18,18,22,0.98)_100%)] dark:shadow-[0_30px_120px_rgba(0,0,0,0.45)]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.10),transparent_35%),radial-gradient(circle_at_top_right,rgba(212,255,18,0.08),transparent_28%)] pointer-events-none dark:bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.18),transparent_35%),radial-gradient(circle_at_top_right,rgba(212,255,18,0.10),transparent_28%)]" />
                <div className="relative p-6 md:p-8 lg:p-10 space-y-6">
                    <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-black/8 bg-black/[0.04] px-4 py-1.5 text-[11px] font-mono uppercase tracking-[0.22em] text-black/45 dark:border-white/10 dark:bg-white/5 dark:text-white/50">AI Forensics Intake</div>
                            <h2 className="mt-4 text-2xl md:text-3xl font-bold text-[#1B1B1F] tracking-tight dark:text-white">多模态检材接入与文本取证协同</h2>
                            <p className="mt-2 max-w-3xl text-sm md:text-base text-black/60 leading-relaxed dark:text-white/60">上层上传多媒体检材，下层补充文本提示、案件背景或分析重点，让多智能体在同一任务上下文中完成鉴伪、溯源与交叉验证。</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 self-start md:self-auto">
                            {aspectOptions.map((option) => (
                                <button key={option} type="button" onClick={() => setSelectedFocus(option)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${selectedFocus === option ? "bg-[#6366F1] text-white shadow-[0_0_20px_rgba(99,102,241,0.20)]" : "border border-black/8 bg-black/[0.04] text-black/55 hover:bg-black/[0.07] dark:border-white/10 dark:bg-white/5 dark:text-white/55 dark:hover:bg-white/10"}`}>{option}</button>
                            ))}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 gap-5">
                        <motion.div
                            onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={onDrop}
                            animate={{
                                borderColor: isDragging ? "rgba(99,102,241,0.85)" : selectedFile ? "rgba(212,255,18,0.45)" : "rgba(255,255,255,0.14)",
                                boxShadow: isDragging ? "0 0 40px rgba(99,102,241,0.25), inset 0 0 40px rgba(99,102,241,0.06)" : selectedFile ? "0 0 30px rgba(212,255,18,0.15)" : "0 12px 40px rgba(0,0,0,0.15)",
                            }}
                            transition={{ duration: 0.2 }}
                            className="rounded-[1.75rem] border border-dashed border-black/8 bg-black/[0.03] p-6 md:p-7 cursor-pointer dark:border-white/14 dark:bg-white/[0.03]"
                            onClick={() => !uploading && document.getElementById("file-input")?.click()}
                        >
                            <input id="file-input" type="file" accept={ACCEPTED_EXT} className="hidden" onChange={onFileChange} />
                            <div className="flex items-start justify-between gap-4 mb-5">
                                <div>
                                    <div className="text-lg md:text-xl font-semibold text-[#1F1F23] dark:text-white">多媒体上传区</div>
                                    <div className="mt-1 text-sm text-black/50 dark:text-white/45">支持视频、音频、图片与文本文件上传，自动识别模态类型并构建证据视图。</div>
                                </div>
                                <div className="text-right text-xs text-black/40 leading-5 dark:text-white/35">支持 MP4 / WebM / MP3 / WAV / JPG / PNG / WebP / TXT<br />单文件最大 500MB</div>
                            </div>

                            <AnimatePresence mode="wait">
                                {uploading ? (
                                    <motion.div key="uploading" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="space-y-5">
                                        <div className="flex justify-center"><Image src="/loading-icon.svg" alt="uploading" width={64} height={64} className="h-16 w-16 animate-pulse" /></div>
                                        <div className="text-center">
                                            <p className="text-[#1F1F23] font-semibold text-lg dark:text-white">{selectedFile?.name || "文本分析任务"}</p>
                                            <p className="text-black/45 text-sm mt-1 dark:text-white/45">{selectedFile ? formatSize(selectedFile.size) : "已提交文本提示词"}</p>
                                        </div>
                                        <div className="w-full bg-black/8 rounded-full h-2 overflow-hidden dark:bg-white/10"><motion.div className="h-full rounded-full bg-gradient-to-r from-[#6366F1] via-[#A855F7] to-[#D4FF12]" initial={{ width: "0%" }} animate={{ width: `${progress}%` }} transition={{ duration: 0.3 }} /></div>
                                        <p className="text-center text-[#789500] text-sm font-mono dark:text-[#D4FF12]">{progress < 100 ? `正在创建检测任务... ${Math.round(progress)}%` : "✓ 已启动多智能体分析"}</p>
                                    </motion.div>
                                ) : (
                                    <motion.div key="idle" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-[1.5rem] border border-black/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.62)_0%,rgba(244,241,236,0.72)_100%)] px-6 py-10 text-center dark:border-white/10 dark:bg-black/20">
                                        <div className="mx-auto mb-5 flex items-center justify-center"><Image src="/loading-icon.svg" alt="upload" width={80} height={80} className="h-20 w-20" /></div>
                                        <p className="text-[#1E1E22] text-xl font-semibold dark:text-white">拖拽或点击上传多媒体检材</p>
                                        <p className="mt-2 text-sm text-black/55 leading-relaxed dark:text-white/50">适合提交视频、音频、图片与截图证据，也可补充原始文本文件。系统会自动进入鉴伪、溯源与证据链建模流程。</p>
                                        <div className="mt-5 flex flex-wrap justify-center gap-2">{["VIDEO", "AUDIO", "IMAGE", "TEXT"].map((type) => <span key={type} className="rounded-full border border-black/8 bg-black/[0.04] px-3 py-1 text-[11px] font-mono text-black/45 dark:border-white/10 dark:bg-white/5 dark:text-white/45">{type}</span>)}</div>
                                        {selectedFile && <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-[#D4FF12]/25 bg-[#D4FF12]/12 px-4 py-2 text-sm text-[#789500] dark:border-[#D4FF12]/20 dark:bg-[#D4FF12]/10 dark:text-[#D4FF12]">已选文件：{selectedFile.name} · {formatSize(selectedFile.size)}</div>}
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>

                        <div className="rounded-[1.75rem] border border-black/8 bg-black/[0.03] p-6 md:p-7 dark:border-white/10 dark:bg-white/[0.03]">
                            <div className="flex items-center justify-between gap-4 mb-4">
                                <div>
                                    <div className="text-lg md:text-xl font-semibold text-[#1F1F23] dark:text-white">文本上传区</div>
                                    <div className="mt-1 text-sm text-black/50 dark:text-white/45">补充案件描述、分析提示、来源背景或明确你最想让系统重点审查的风险点。</div>
                                </div>
                                <button type="button" onClick={() => setTextPrompt(promptTemplates[0])} className="rounded-xl border border-[#6366F1]/20 bg-[#6366F1]/8 px-4 py-2 text-sm font-medium text-[#4F46E5] hover:bg-[#6366F1]/12 transition-colors dark:border-[#6366F1]/25 dark:bg-[#6366F1]/12 dark:text-[#C7C9FF] dark:hover:bg-[#6366F1]/18">提示词模板</button>
                            </div>
                            <textarea value={textPrompt} onChange={(e) => setTextPrompt(e.target.value)} placeholder="例如：请重点判断该视频是否存在换脸、合成语音与传播链异常，并输出关键证据与处置建议。" className="min-h-[180px] w-full resize-none rounded-[1.25rem] border border-black/8 bg-white/60 px-5 py-4 text-base leading-7 text-[#1F1F23] placeholder:text-black/30 focus:outline-none focus:ring-2 focus:ring-[#6366F1]/25 focus:border-[#6366F1]/30 transition-all dark:border-white/10 dark:bg-black/20 dark:text-white dark:placeholder:text-white/25 dark:focus:ring-[#6366F1]/40 dark:focus:border-[#6366F1]/40" />
                            <div className="mt-5 flex flex-wrap gap-2">{promptTemplates.map((template) => <button key={template} type="button" onClick={() => setTextPrompt(template)} className="rounded-full border border-black/8 bg-black/[0.04] px-3 py-1.5 text-xs text-black/55 hover:bg-black/[0.07] hover:text-black transition-colors dark:border-white/10 dark:bg-white/5 dark:text-white/55 dark:hover:bg-white/10 dark:hover:text-white">{template.slice(0, 14)}...</button>)}</div>
                        </div>
                    </div>

                    <div className="rounded-[1.75rem] border border-black/8 bg-black/[0.03] p-5 md:p-6 dark:border-white/10 dark:bg-white/[0.03]">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                            <div className="flex flex-wrap items-center gap-3">
                                <button type="button" onClick={() => launchAnalysis(selectedFile, textPrompt)} disabled={uploading} className="inline-flex items-center justify-center rounded-2xl bg-gradient-to-r from-[#8B5CF6] via-[#A855F7] to-[#EC4899] px-8 py-3 text-sm md:text-base font-semibold text-white shadow-[0_10px_40px_rgba(168,85,247,0.35)] transition-transform hover:scale-[1.02] disabled:opacity-60 disabled:cursor-not-allowed">开始分析</button>
                                <button type="button" onClick={() => setTextPrompt("")} disabled={uploading} className="rounded-2xl border border-black/8 bg-black/[0.04] px-5 py-3 text-sm font-medium text-black/70 hover:bg-black/[0.07] hover:text-black transition-colors disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white">清空提示词</button>
                                <button type="button" onClick={() => setTextPrompt(promptTemplates[1])} disabled={uploading} className="rounded-2xl border border-[#6366F1]/18 bg-[#6366F1]/8 px-5 py-3 text-sm font-medium text-[#4F46E5] hover:bg-[#6366F1]/12 transition-colors disabled:opacity-50 dark:border-[#6366F1]/20 dark:bg-[#6366F1]/10 dark:text-[#C7C9FF] dark:hover:bg-[#6366F1]/18">使用模板</button>
                            </div>
                            <label className="flex items-center gap-3 rounded-2xl border border-black/8 bg-white/55 px-4 py-3 cursor-pointer dark:border-white/10 dark:bg-black/20">
                                <input type="checkbox" checked={shareToCasebase} onChange={(e) => setShareToCasebase(e.target.checked)} className="h-4 w-4 rounded border-black/20 bg-transparent accent-[#D4FF12] dark:border-white/20" />
                                <div>
                                    <div className="text-sm font-medium text-[#1F1F23] dark:text-white">愿意脱敏后公开至案例库</div>
                                    <div className="text-xs text-black/45 mt-0.5 dark:text-white/40">仅同步匿名化结果、关键证据摘要与可复用分析路径</div>
                                </div>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
            <AnimatePresence>{error && <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 text-[#EF4444] text-sm text-center">⚠️ {error}</motion.p>}</AnimatePresence>
        </div>
    )
}
