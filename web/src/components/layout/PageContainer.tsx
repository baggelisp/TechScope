export type PageContainerProps = {
    children: React.ReactNode
}

/** The one place the page's outer rhythm is decided, so no page brings its own. */
const PageContainer = ({ children }: PageContainerProps) => {
    return (
        <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-3 py-6 sm:gap-8 sm:px-6 sm:py-10">
            {children}
        </main>
    )
}

export default PageContainer
