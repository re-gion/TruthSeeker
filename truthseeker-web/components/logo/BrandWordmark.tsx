import type { ComponentPropsWithoutRef } from "react"

type BrandWordmarkProps = ComponentPropsWithoutRef<"span">

export function BrandWordmark({
  children = "TruthSeeker",
  className,
  ...props
}: BrandWordmarkProps) {
  return (
    <span
      className={["brand-wordmark", className].filter(Boolean).join(" ")}
      {...props}
    >
      {children}
    </span>
  )
}
