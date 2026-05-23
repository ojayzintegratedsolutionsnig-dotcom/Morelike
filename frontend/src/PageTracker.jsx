import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID

export default function PageTracker() {
  const location = useLocation()

  useEffect(() => {
    if (!MEASUREMENT_ID || !window.gtag) return
    window.gtag('config', MEASUREMENT_ID, {
      page_path: location.pathname + location.search,
      page_title: document.title
    })
  }, [location])

  return null
}
