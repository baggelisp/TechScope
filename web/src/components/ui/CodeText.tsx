export type CodeTextProps = {
    children: React.ReactNode
}

const CodeText = ({ children }: CodeTextProps) => {
    return (
        <code className="break-all rounded-md bg-canvas px-2 py-1 font-mono text-xs text-ink">
            {children}
        </code>
    )
}

export default CodeText
