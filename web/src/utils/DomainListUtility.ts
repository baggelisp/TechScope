/**
 * Turning what someone typed or dropped into the list the scanner is asked for.
 *
 * The scanner normalises again on its side, and its answer is the one that counts; this exists
 * so the form can say how many domains it is about to send before it sends them.
 */

const COMMENT_PREFIX = '#'

class DomainListUtility {
    static parse(text: string): string[] {
        const lines = text.split(/\r?\n/)
        const entries = lines.map((line) => line.trim()).filter(DomainListUtility.isUsable)

        return Array.from(new Set(entries))
    }

    static count(text: string): number {
        return DomainListUtility.parse(text).length
    }

    /** The first usable domain in this text, for a route that is about exactly one. */
    static decideFirstOrNull(text: string): string | null {
        const first = DomainListUtility.parse(text)[0]

        if (first) return first

        return null
    }

    /** A domain cannot be longer than this, so a longer line is something else entirely. */
    static hasEntryLongerThan(text: string, maximumLength: number): boolean {
        return DomainListUtility.parse(text).some((entry) => entry.length > maximumLength)
    }

    private static isUsable(line: string): boolean {
        const isEmpty = line.length === 0
        const isComment = line.startsWith(COMMENT_PREFIX)

        if (isEmpty || isComment) return false

        return true
    }
}

export default DomainListUtility
