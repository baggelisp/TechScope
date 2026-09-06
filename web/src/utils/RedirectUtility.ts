/**
 * Whether a scan ended up somewhere other than the domain it was asked about.
 *
 * Compared by host, not by substring: `https://example.com.evil.tld/` contains `example.com`,
 * and a substring test would quietly decide that was the same site. Four of the assignment's own
 * domains really do redirect to the company that acquired them, so getting this wrong hides the
 * one thing that makes those detections honest.
 */

const WWW_PREFIX = 'www.'

class RedirectUtility {
    static decideRedirectOrNull(domain: string, observedUrl: string | null): string | null {
        if (observedUrl) return RedirectUtility.decideDifferentHostOrNull(domain, observedUrl)

        return null
    }

    private static decideDifferentHostOrNull(domain: string, observedUrl: string): string | null {
        const observedHost = RedirectUtility.decideHostOrNull(observedUrl)

        // An unparseable URL is reported rather than hidden: silence is the dangerous answer.
        if (observedHost && observedHost === RedirectUtility.stripWww(domain.toLowerCase())) {
            return null
        }

        return observedUrl
    }

    private static decideHostOrNull(url: string): string | null {
        try {
            return RedirectUtility.stripWww(new URL(url).hostname.toLowerCase())
        } catch {
            return null
        }
    }

    private static stripWww(host: string): string {
        if (host.startsWith(WWW_PREFIX)) return host.slice(WWW_PREFIX.length)

        return host
    }
}

export default RedirectUtility
