'use client'

import type { ScanReport } from '@/api/schemas'
import Button from '@/components/ui/Button'
import { COPY } from '@/constants/copy.constant'
import {
    OUTPUT_FILE_NAME,
    OUTPUT_INDENT_SPACES,
    OUTPUT_MEDIA_TYPE,
} from '@/constants/scan.constant'
import DownloadUtility from '@/utils/DownloadUtility'
import ScanReportUtility from '@/utils/ScanReportUtility'

export type ScanResultsDownloadButtonProps = {
    report: ScanReport | null
}

/**
 * The assignment's own output shape, rebuilt here so the page hands over the graded artefact.
 *
 * The only client component on this page: building a file and handing it to the browser is the
 * one thing here that cannot happen on the server.
 */
const ScanResultsDownloadButton = ({ report }: ScanResultsDownloadButtonProps) => {
    const handleClick = () => {
        if (report) {
            const summary = ScanReportUtility.buildSummaryOutput(report)
            const contents = `${JSON.stringify(summary, null, OUTPUT_INDENT_SPACES)}\n`

            DownloadUtility.saveText(OUTPUT_FILE_NAME, OUTPUT_MEDIA_TYPE, contents)
        }
    }

    if (report) {
        return (
            <Button variant="secondary" onClick={handleClick}>
                {COPY.resultsDownload}
            </Button>
        )
    }

    return null
}

export default ScanResultsDownloadButton
