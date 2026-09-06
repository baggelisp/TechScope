import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
    // A self-contained server directory, so the runtime image carries no node_modules tree.
    output: 'standalone',
    // The app is served from a container that must not be able to write to its own filesystem.
    poweredByHeader: false,
}

export default nextConfig
