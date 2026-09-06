'use server'

/**
 * Running one scan. The only code in this app that knows the scanner's API exists.
 *
 * It runs on the server, so the browser never learns the API's address and there is no CORS to
 * arrange. What comes back is parsed before it is returned: a response that does not match the
 * schema is a failure with a code, not a shape the components have to defend against.
 */

import { scanReportSchema, apiErrorSchema, type ScanReport } from '@/api/schemas'
import {
    ERROR_CODE,
    AppError,
    handleActionError,
    type ActionResponse,
    type ErrorCode,
} from '@/lib/utils/errors'
import { MAXIMUM_SUBMITTED_DOMAINS } from '@/constants/scan.constant'

const DEFAULT_API_URL = 'http://localhost:8000'
const SCANS_PATH = '/scans'
const JSON_MEDIA_TYPE = 'application/json'
// The API's own deadline is 80 s; this gives it room to answer rather than cutting it off first.
const REQUEST_TIMEOUT_MILLISECONDS = 120_000
const TIMEOUT_ERROR_NAME = 'TimeoutError'

export type RunScanInput = {
    domains: string[]
}

export const runScan = async (input: RunScanInput): Promise<ActionResponse<ScanReport>> => {
    try {
        checkDomainsAreWithinTheCapOrThrowError(input.domains)

        const response = await postScan(input)
        const body: unknown = await response.json()

        if (response.ok) {
            const parsed = scanReportSchema.safeParse(body)

            if (parsed.success) return { success: true, data: parsed.data }

            throw new AppError(
                'The scanner answered in a shape this app does not understand.',
                ERROR_CODE.unexpected,
            )
        }

        throw decideApiError(body)
    } catch (error) {
        return handleActionError(error)
    }
}

const postScan = async (input: RunScanInput): Promise<Response> => {
    try {
        return await fetch(`${decideApiUrl()}${SCANS_PATH}`, {
            method: 'POST',
            headers: { 'content-type': JSON_MEDIA_TYPE },
            body: JSON.stringify({ domains: input.domains }),
            cache: 'no-store',
            signal: AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS),
        })
    } catch (error) {
        throw new AppError(decideTransportMessage(error), ERROR_CODE.serviceUnavailable)
    }
}

const decideTransportMessage = (error: unknown): string => {
    if (error instanceof DOMException && error.name === TIMEOUT_ERROR_NAME) {
        return 'The scan took longer than this app waits for it.'
    }

    return 'The scanner is not answering. Is the API running?'
}

const decideApiError = (body: unknown): AppError => {
    const parsed = apiErrorSchema.safeParse(body)

    if (parsed.success) {
        return new AppError(parsed.data.error.message, decideErrorCode(parsed.data.error.code))
    }

    return new AppError('The scanner refused the request.', ERROR_CODE.unexpected)
}

const decideErrorCode = (code: string): ErrorCode => {
    const known = Object.values(ERROR_CODE).find((value) => value === code)

    if (known) return known

    return ERROR_CODE.unexpected
}

const decideApiUrl = (): string => {
    const configured = process.env.API_URL

    if (configured) return configured

    return DEFAULT_API_URL
}

function checkDomainsAreWithinTheCapOrThrowError(domains: string[]): void {
    if (domains.length === 0) {
        throw new AppError('Enter at least one domain.', ERROR_CODE.invalidRequest)
    }

    if (domains.length > MAXIMUM_SUBMITTED_DOMAINS) {
        throw new AppError(
            `A scan may cover at most ${MAXIMUM_SUBMITTED_DOMAINS} domains, and ${domains.length} were entered.`,
            ERROR_CODE.invalidRequest,
        )
    }
}
