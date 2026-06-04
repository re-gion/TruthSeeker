// @vitest-environment jsdom

import React from "react"
import "@testing-library/jest-dom/vitest"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { HeaderClient } from "./HeaderClient"

vi.mock("next/image", () => ({
  default: ({ alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={alt} {...props} />,
}))

vi.mock("@/components/logo/BrandLogo", () => ({
  BrandLogo: () => <div data-testid="brand-logo" />,
}))

vi.mock("@/components/landing/ThemeToggle", () => ({
  ThemeToggle: () => <button type="button">切换主题</button>,
}))

vi.mock("@/components/ui/ShinyText", () => ({
  default: ({ text }: { text: string }) => <span>{text}</span>,
}))

describe("HeaderClient", () => {
  it("exposes a navigation entry for the personal experience library", () => {
    render(<HeaderClient user={{ email: "user@example.test" }} />)

    expect(screen.getByRole("link", { name: /个人经验库/ })).toHaveAttribute("href", "/experiences")
    expect(screen.getByRole("img", { name: "个人经验库图标" })).toHaveAttribute("src", "/nav-icons/experiences.svg")
  })
})
