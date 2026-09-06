import ButtonRow from '@/components/ui/ButtonRow'
import Card from '@/components/ui/Card'
import LinkButton from '@/components/ui/LinkButton'
import { COPY } from '@/constants/copy.constant'
import { ROUTE } from '@/constants/route.constant'

export type PageErrorProps = {
    title: string
    message: string
    code: string
}

/** What a page renders instead of itself when the thing it exists to show is not there. */
const PageError = ({ title, message, code }: PageErrorProps) => {
    return (
        <Card tone="danger">
            <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-peach">{title}</h2>
                    <p className="text-sm text-ink">{message}</p>
                    <code className="text-xs text-ink-faint">{code}</code>
                </div>
                <ButtonRow>
                    <LinkButton href={ROUTE.scanForm} variant="danger">
                        {COPY.errorRetry}
                    </LinkButton>
                </ButtonRow>
            </div>
        </Card>
    )
}

export default PageError
