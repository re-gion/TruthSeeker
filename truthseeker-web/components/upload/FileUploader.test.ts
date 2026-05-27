import { describe, expect, it } from "vitest"

import { getUploadErrorMessage } from "./FileUploader"

describe("getUploadErrorMessage", () => {
  it("explains backend connectivity failures instead of showing raw Failed to fetch", () => {
    const message = getUploadErrorMessage(new TypeError("Failed to fetch"), "http://localhost:8000")

    expect(message).toContain("后端服务未连接")
    expect(message).toContain("http://localhost:8000")
    expect(message).not.toContain("Failed to fetch")
  })
})
