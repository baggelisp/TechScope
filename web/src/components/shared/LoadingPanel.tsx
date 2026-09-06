import Card from '@/components/ui/Card'
import Spinner from '@/components/ui/Spinner'

export type LoadingPanelProps = {
    title: string
    message: string
}

const LoadingPanel = ({ title, message }: LoadingPanelProps) => {
    return (
        <Card tone="plain">
            <div className="flex items-start gap-4">
                <div className="mt-1 flex">
                    <Spinner />
                </div>
                <div className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-ink">{title}</h2>
                    <p className="text-sm text-ink-muted">{message}</p>
                </div>
            </div>
        </Card>
    )
}

export default LoadingPanel
