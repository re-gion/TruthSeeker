// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { describe, expect, it } from "vitest"

import { BrandWordmark } from "./BrandWordmark"

describe("BrandWordmark", () => {
  it("renders the TruthSeeker brand name with the dedicated wordmark class", () => {
    render(<BrandWordmark className="text-xl" />)

    const wordmark = screen.getByText("TruthSeeker")
    expect(wordmark).toHaveClass("brand-wordmark", "text-xl")
  })

  it("supports inline brand-name content without changing surrounding typography", () => {
    render(<BrandWordmark>TruthSeeker Data Screen</BrandWordmark>)

    expect(screen.getByText("TruthSeeker Data Screen")).toHaveClass("brand-wordmark")
  })
})
