// Index configuration objects for the generic option chain component

export const NIFTY_CONFIG = {
	displayName: 'NIFTY 50',
	symbol: 'NIFTY',
	exchangeCode: 'NFO',
	apiEndpoint: '/api/option-chain/nifty-strikes',
	atmThreshold: 25, // ATM if within 25 points (for 50-point intervals)
	defaultPrice: 24741,
	interval: 50 // Strike price interval
}

export const BANKNIFTY_CONFIG = {
	displayName: 'BANK NIFTY',
	symbol: 'BANKNIFTY',
	exchangeCode: 'NFO',
	apiEndpoint: '/api/option-chain/banknifty-strikes',
	atmThreshold: 50, // ATM if within 50 points (for 100-point intervals)
	defaultPrice: 52000,
	interval: 100 // Strike price interval
}

// Future indices can be easily added here
export const FINNIFTY_CONFIG = {
	displayName: 'FIN NIFTY',
	symbol: 'FINNIFTY',
	exchangeCode: 'NFO',
	apiEndpoint: '/api/option-chain/finnifty-strikes',
	atmThreshold: 25, // ATM if within 25 points (for 50-point intervals)
	defaultPrice: 20000,
	interval: 50 // Strike price interval
}

// Export all configs as an object for easy access
export const INDEX_CONFIGS = {
	NIFTY: NIFTY_CONFIG,
	BANKNIFTY: BANKNIFTY_CONFIG,
	FINNIFTY: FINNIFTY_CONFIG
}
