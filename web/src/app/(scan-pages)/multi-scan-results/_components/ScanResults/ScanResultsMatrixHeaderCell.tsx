export type ScanResultsMatrixHeaderCellProps = {
    technology: string
}

const ScanResultsMatrixHeaderCell = ({ technology }: ScanResultsMatrixHeaderCellProps) => {
    return (
        <th
            scope="col"
            className="whitespace-nowrap px-3 py-3 text-center text-xs font-semibold text-ink-muted"
        >
            {technology}
        </th>
    )
}

export default ScanResultsMatrixHeaderCell
