const INPUT_TYPE_LABELS: Record<string, string> = {
  text: "文本内容",
  image: "图像内容",
  audio: "音频内容",
  video: "视频内容",
  text_image: "图文混合",
  text_audio: "文本+音频",
  text_video: "文本+视频",
  image_audio: "图像+音频",
  image_video: "图像+视频",
  audio_video: "音频+视频",
  text_image_audio: "文本+图像+音频",
  text_image_video: "文本+图像+视频",
  text_audio_video: "文本+音频+视频",
  image_audio_video: "图像+音频+视频",
  text_image_audio_video: "文本+图像+音频+视频",
}

const LEGACY_ALIASES: Record<string, string> = {
  mixed: "text_image",
  image_text: "text_image",
  image_text_mixed: "text_image",
}

export function displayInputType(value: string | null | undefined): string {
  const raw = (value ?? "").trim()
  const key = raw.toLowerCase().replace(/\s+/g, "").replace(/-/g, "_")
  const normalized = LEGACY_ALIASES[key] ?? key
  return INPUT_TYPE_LABELS[normalized] ?? raw
}
