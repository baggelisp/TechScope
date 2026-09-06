/**
 * Every string a person reads, in one place.
 *
 * The app ships in one language, so it carries no translation library; keeping the copy out of
 * the markup is what that rule is really for, and it costs one file instead of a dependency.
 */

export const COPY = {
    appTitle: 'TechScope',
    appKicker: 'Technographic scanner',
    appTagline: 'See what a website is built with, and the evidence for every answer.',
    heroHeadline: 'See what a website is built with.',
    heroBody:
        'Paste a list of domains. Every technology comes back with the signal that proved it, so you can check the answer yourself.',

    formHeading: 'Domains to scan',
    formHint: 'One per line. Schemes, www and paths are stripped for you.',
    formLimitHint: 'Up to 50 domains. The scanner sets how many run at once.',
    formReadyToScan: ' ready to scan.',
    formOverTheCap: ' entered. The scanner accepts 50.',
    formEntryTooLong: 'One of these lines is far too long to be a domain.',
    formPlaceholder: 'stripe.com\nshopify.com\nnotion.so',
    formFileButton: 'Load a .txt file',
    formFileDropHint: 'or drop a .txt file anywhere on this panel',
    formSubmit: 'Scan',
    formSubmitPending: 'Scanning…',
    formClear: 'Clear',

    resultsHeading: 'Results',
    resultsNewScan: 'New scan',
    backToForm: 'Back to scan',
    backToResults: 'Back to results',
    resultsDownload: 'Download output.json',
    resultsEmpty: 'No technology was detected on any of these domains.',
    resultsMatrixDomainHeader: 'Domain',
    resultsRedirectPrefix: 'read from',
    resultsProblemsHeading: 'Domains that did not answer cleanly',
    resultsNoDetections: 'nothing detected',
    resultsBlankCell: '\u2014',
    resultsProblemSeparator: ' \u00b7 ',
    resultsProblemDetailSeparator: '. ',

    evidenceHeading: 'Why this was reported',
    evidenceConfidence: 'confidence',
    evidencePattern: 'Pattern',
    evidenceMatched: 'Matched',
    evidenceKey: 'Key',
    evidenceClose: 'Close',
    evidenceOnJoiner: ' on ',
    evidenceLabelJoiner: ', ',

    summaryDomains: 'Domains',
    summaryDetections: 'Detections',
    summaryProblems: 'With problems',
    summarySeconds: 'Seconds',

    pendingHeading: 'Scanning',
    pendingBody: 'Every domain is fetched once and its DNS records read. This takes a few seconds.',

    errorHeading: 'The scan did not run',
    errorRetry: 'Try again',
    errorNoDomainCode: 'no_result',
    channelsHeading: 'What it reads',
    channelsBody:
        'Response headers, cookies, script URLs, inline scripts, meta tags, JavaScript globals and DNS records on the apex.',
    domainHeadingSuffix: 'What this domain runs',
    domainBackToResults: 'Back to results',
    domainReadFrom: 'Page read',
    domainDuration: 'Seconds',
    domainDetections: 'Detections',
    domainSignals: 'Signals',
    domainEmpty: 'Nothing detectable was found on this domain.',
    domainProblemsHeading: 'Problems',
    domainEvidenceHeading: 'Evidence',
    domainTechnologiesHeading: 'Technologies found',
    domainSignalsShort: 'signals',
    domainDetailHeading: 'Where each answer came from',
    domainSameHost: 'the domain itself',
} as const
