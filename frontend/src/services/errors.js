export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(item => item?.msg || 'Invalid input').join(' · ')
  if (error?.code === 'ECONNABORTED') return 'The server is taking longer than expected. Please retry shortly.'
  return error?.message || fallback
}
