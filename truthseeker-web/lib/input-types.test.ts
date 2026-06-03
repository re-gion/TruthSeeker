import { describe, expect, it } from "vitest"

import { displayInputType } from "./input-types"

describe("displayInputType", () => {
  it("maps legacy mixed and canonical combinations to concrete labels", () => {
    expect(displayInputType("mixed")).toBe("图文混合")
    expect(displayInputType("text_image")).toBe("图文混合")
    expect(displayInputType("text_audio_video")).toBe("文本+音频+视频")
  })
})
