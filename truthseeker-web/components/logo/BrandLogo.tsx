import Image from "next/image"

import mainLogo from "./（主logo）logo3-上部-透明.png"
import transitionDarkLogo from "./(深色背景切页动画用)logo3-完全+不透明.png"
import transitionLightLogo from "./（浅色背景切页动画）logo3-完全-不透明+纯白背景.png"

type BrandLogoVariant = "main" | "transition-dark" | "transition-light"

const LOGO_SOURCE: Record<BrandLogoVariant, typeof mainLogo> = {
  main: mainLogo,
  "transition-dark": transitionDarkLogo,
  "transition-light": transitionLightLogo,
}

interface BrandLogoProps {
  variant?: BrandLogoVariant
  className?: string
  imageClassName?: string
  size?: number
  priority?: boolean
  alt?: string
}

export function BrandLogo({
  variant = "main",
  className,
  imageClassName,
  size = 40,
  priority = false,
  alt = "TruthSeeker logo",
}: BrandLogoProps) {
  return (
    <span className={className}>
      <Image
        src={LOGO_SOURCE[variant]}
        alt={alt}
        width={size}
        height={size}
        priority={priority}
        className={`h-full w-full object-contain ${imageClassName ?? ""}`}
      />
    </span>
  )
}
