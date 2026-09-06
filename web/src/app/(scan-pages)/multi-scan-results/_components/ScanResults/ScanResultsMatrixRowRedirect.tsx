import { COPY } from '@/constants/copy.constant'

export type ScanResultsMatrixRowRedirectProps = {
    redirect: string | null
}

const ScanResultsMatrixRowRedirect = ({ redirect }: ScanResultsMatrixRowRedirectProps) => {
    if (redirect) {
        return (
            <span className="text-xs font-normal text-peach">
                {COPY.resultsRedirectPrefix} {redirect}
            </span>
        )
    }

    return null
}

export default ScanResultsMatrixRowRedirect
