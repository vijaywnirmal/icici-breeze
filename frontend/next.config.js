export default {
	reactStrictMode: true,
	webpack: (config) => {
		config.resolve.extensions.push('.jsx', '.js', '.tsx', '.ts')
		return config
	},
	async rewrites() {
		const target = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'
		return [
			{
				source: '/api/:path*',
				destination: `${target}/api/:path*`,
			},
		]
	},
}

