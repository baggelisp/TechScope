import ScanResultsMatrixHeader from './ScanResultsMatrixHeader'
import ScanResultsMatrixRowList from './ScanResultsMatrixRowList'
import type { DomainResult } from '@/api/schemas'

export type ScanResultsMatrixProps = {
    domains: DomainResult[]
    technologies: string[]
}

const ScanResultsMatrix = ({ domains, technologies }: ScanResultsMatrixProps) => {
    if (technologies.length > 0) {
        return (
            <div className="overflow-x-auto rounded-xl border border-line bg-surface">
                <table className="w-full border-collapse text-sm">
                    <ScanResultsMatrixHeader technologies={technologies} />
                    <ScanResultsMatrixRowList domains={domains} technologies={technologies} />
                </table>
            </div>
        )
    }

    return null
}

export default ScanResultsMatrix
