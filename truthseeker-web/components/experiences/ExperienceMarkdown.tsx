import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface ExperienceMarkdownProps {
  children: string
  className?: string
}

export function ExperienceMarkdown({ children, className = "" }: ExperienceMarkdownProps) {
  return (
    <div className={`experience-markdown ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}
