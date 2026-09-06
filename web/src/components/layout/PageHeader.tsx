export type PageHeaderProps = {
    title: string
    subtitle: string
    action: React.ReactNode
}

const PageHeader = ({ title, subtitle, action }: PageHeaderProps) => {
    return (
        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-1">
                <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
                <p className="text-sm text-ink-muted">{subtitle}</p>
            </div>
            {action}
        </header>
    )
}

export default PageHeader
