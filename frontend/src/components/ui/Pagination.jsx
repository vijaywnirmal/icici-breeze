import React from 'react'
import Button from './Button'

export default function Pagination({ page = 1, pageCount = 1, onPageChange }) {
	const canPrev = page > 1
	const canNext = page < pageCount
	return (
		<div className="flex items-center justify-between gap-2 mt-3">
			<Button variant="secondary" size="sm" disabled={!canPrev} onClick={() => canPrev && onPageChange(page - 1)}>
				Prev
			</Button>
			<div className="text-sm text-slate-300">
				Page <span className="font-semibold text-white">{page}</span> of <span className="font-semibold text-white">{pageCount}</span>
			</div>
			<Button variant="secondary" size="sm" disabled={!canNext} onClick={() => canNext && onPageChange(page + 1)}>
				Next
			</Button>
		</div>
	)
}


