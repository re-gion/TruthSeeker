import { describe, expect, it } from "vitest"

import { deriveInputType, getCasebaseFileSizeError, getUploadErrorMessage } from "./FileUploader"

describe("getUploadErrorMessage", () => {
  it("explains backend connectivity failures instead of showing raw Failed to fetch", () => {
    const message = getUploadErrorMessage(new TypeError("Failed to fetch"), "http://localhost:8000")

    expect(message).toContain("后端服务未连接")
    expect(message).toContain("http://localhost:8000")
    expect(message).not.toContain("Failed to fetch")
  })
})

describe("getCasebaseFileSizeError", () => {
  it("blocks files over 50MB only when public case sharing is enabled", () => {
    const largeFile = new File(["x"], "large.mp4", { type: "video/mp4" })
    Object.defineProperty(largeFile, "size", { value: 51 * 1024 * 1024 })

    expect(getCasebaseFileSizeError([largeFile], true)).toContain("公开案例库")
    expect(getCasebaseFileSizeError([largeFile], false)).toBeNull()
  })
})

describe("deriveInputType", () => {
  it("returns canonical modality combinations instead of mixed", () => {
    expect(deriveInputType([
      { id: "1", name: "notice.png", mime_type: "image/png", size_bytes: 1, modality: "image", storage_path: "a" },
      { id: "2", name: "claim.txt", mime_type: "text/plain", size_bytes: 1, modality: "text", storage_path: "b" },
    ])).toBe("text_image")

    expect(deriveInputType([
      { id: "1", name: "voice.mp3", mime_type: "audio/mpeg", size_bytes: 1, modality: "audio", storage_path: "a" },
      { id: "2", name: "clip.mp4", mime_type: "video/mp4", size_bytes: 1, modality: "video", storage_path: "b" },
    ])).toBe("audio_video")
  })
})
