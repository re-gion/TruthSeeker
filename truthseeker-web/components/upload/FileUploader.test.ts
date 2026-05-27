import { describe, expect, it } from "vitest"

import { getCasebaseFileSizeError, getUploadErrorMessage } from "./FileUploader"

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
