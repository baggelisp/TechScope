/**
 * One shape for everything a server action can answer with.
 *
 * An action never throws at its caller: a component should branch on a result, not wrap every
 * call in a try/catch. The scanner's own API already answers failures as
 * `{ error: { code, message } }`, so a code that crosses the network arrives here intact.
 */

export const ERROR_CODE = {
    invalidRequest: 'invalid_request',
    serviceUnavailable: 'service_unavailable',
    internalError: 'internal_error',
    unexpected: 'error',
} as const

export type ErrorCode = (typeof ERROR_CODE)[keyof typeof ERROR_CODE]

export type ActionError = {
    message: string
    code: ErrorCode
}

export type ActionResponse<T> =
    | { success: true; data: T }
    | { success: false; error: ActionError }

export class AppError extends Error {
    readonly code: ErrorCode

    constructor(message: string, code: ErrorCode) {
        super(message)
        this.name = 'AppError'
        this.code = code
    }
}

export const buildActionFailure = (error: ActionError): ActionResponse<never> => {
    return { success: false, error }
}

export const handleActionError = (error: unknown): ActionResponse<never> => {
    if (error instanceof AppError) {
        return buildActionFailure({ message: error.message, code: error.code })
    }

    console.error('unexpected failure in a server action', error)

    return buildActionFailure({
        message: 'The scan could not be completed.',
        code: ERROR_CODE.unexpected,
    })
}
