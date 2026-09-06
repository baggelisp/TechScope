/** Reading a report: the shapes the results view needs that the API does not hand over ready. */

import type { DomainResult, Detection, ScanReport } from '@/api/schemas'

class ScanReportUtility {
    /** Every technology found anywhere in the run, sorted, so the matrix has stable columns. */
    static listTechnologyNames(report: ScanReport): string[] {
        const names = report.domains.flatMap((domain) => domain.technologies)

        return Array.from(new Set(names)).sort((left, right) => left.localeCompare(right))
    }

    static decideDetectionOrNull(domain: DomainResult, technology: string): Detection | null {
        const detection = domain.detections.find((candidate) => candidate.name === technology)

        if (detection) return detection

        return null
    }

    static listTroubledDomains(report: ScanReport): DomainResult[] {
        return report.domains.filter((domain) => domain.problems.length > 0)
    }

    /** The shape the assignment asks for, rebuilt in the browser from what the API returned. */
    static buildSummaryOutput(report: ScanReport): Record<string, string[]> {
        const output: Record<string, string[]> = {}

        for (const domain of report.domains) {
            output[domain.domain] = domain.technologies
        }

        return output
    }
}

export default ScanReportUtility
