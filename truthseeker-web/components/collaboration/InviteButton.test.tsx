// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { InviteButton } from "./InviteButton"

vi.mock("@/lib/auth", () => ({
    getAuthToken: vi.fn(async () => "token-1"),
}))

vi.mock("motion/react", () => ({
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: {
        div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
    },
}))

describe("InviteButton", () => {
    it("retries a transient fetch failure and copies the invite link", async () => {
        const writeText = vi.fn()
        Object.assign(navigator, { clipboard: { writeText } })
        const fetchMock = vi.fn()
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ invite_url: "/detect/task-1?role=expert&invite_token=abc" }),
            })
        vi.stubGlobal("fetch", fetchMock)

        render(<InviteButton taskId="task-1" />)
        fireEvent.click(screen.getByRole("button", { name: /邀请专家会诊/ }))

        await waitFor(() => {
            expect(writeText).toHaveBeenCalledWith("http://localhost:3000/detect/task-1?role=expert&invite_token=abc")
        }, { timeout: 1500 })
        expect(fetchMock).toHaveBeenCalledTimes(2)
    })

    it("ignores a second click while invite creation is pending", async () => {
        const writeText = vi.fn()
        Object.assign(navigator, { clipboard: { writeText } })
        let resolveFetch: (value: Response) => void = () => {}
        const fetchMock = vi.fn(() => new Promise<Response>(resolve => {
            resolveFetch = resolve
        }))
        vi.stubGlobal("fetch", fetchMock)

        render(<InviteButton taskId="task-1" />)
        const button = screen.getByRole("button", { name: /邀请专家会诊/ })
        fireEvent.click(button)
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledTimes(1)
        })
        fireEvent.click(button)

        expect(fetchMock).toHaveBeenCalledTimes(1)
        resolveFetch({
            ok: true,
            json: async () => ({ invite_url: "/detect/task-1?role=expert&invite_token=abc" }),
        } as Response)

        await waitFor(() => {
            expect(writeText).toHaveBeenCalledTimes(1)
        })
    })
})
