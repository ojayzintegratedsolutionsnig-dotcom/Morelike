import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { jsPDF } from 'jspdf'

const API_URL = import.meta.env.VITE_API_URL || 'https://morelike-morelike.up.railway.app'
const LEMON_SQUEEZY_URL = import.meta.env.VITE_LEMON_SQUEEZY_URL || 'https://morelike.lemonsqueezy.com/checkout/buy/a6315998-f19d-4806-ba57-a40dd789348b'

const getApiHeaders = (token) => ({
  'Content-Type': 'application/json',
  ...(token ? { 'Authorization': `Bearer ${token}` } : {})
})

/* ── Animated progress bar ──────────────────────────────────── */
function ProgressBar() {
  return (
    <div className="w-full max-w-md mx-auto py-8">
      <div className="relative w-full h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className="absolute inset-0 bg-gradient-to-r from-purple-500 via-pink-500 to-purple-500 bg-[length:200%_100%] animate-shimmer rounded-full"
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}

/* ── Title selection ────────────────────────────────────────── */
function TitlePicker({ titles, onChoose, onRegenerate, loading }) {
  const [customTopic, setCustomTopic] = useState('')

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Choose Your Title</h2>
      <p className="text-purple-200">Pick the one that fits your niche best.</p>

      <div className="space-y-3 mt-6">
        {titles.map((title, i) => (
          <button
            key={i}
            onClick={() => onChoose(title, customTopic)}
            className="w-full text-left p-3 md:p-4 rounded-lg border transition-all bg-gray-900/50 border-gray-700 hover:border-purple-500/50 hover:bg-gray-800/50 group"
          >
            <span className="text-purple-400 font-bold mr-3 group-hover:text-purple-300">#{i + 1}</span>
            <span className="text-white">{title}</span>
          </button>
        ))}
      </div>

      <div className="border-t border-gray-700 pt-4 mt-6">
        <label className="block text-sm text-purple-200 mb-2">Optional: add your own angle or topic</label>
        <input
          type="text"
          placeholder="e.g., The hidden psychology behind..."
          value={customTopic}
          onChange={(e) => setCustomTopic(e.target.value)}
          className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        />
      </div>

      <button
        onClick={onRegenerate}
        disabled={loading}
        className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white rounded-lg transition-all text-sm disabled:opacity-50"
      >
        {loading ? 'Regenerating...' : 'Regenerate Titles'}
      </button>
    </div>
  )
}

/* ── Paywall modal ──────────────────────────────────────────── */
const LEMON_SQUEEZY_URL_PRO = import.meta.env.VITE_LEMON_SQUEEZY_URL_PRO || 'https://morelike.lemonsqueezy.com/checkout/buy/5562929e-ce1b-4f28-a35b-90dce4371804'
const LEMON_SQUEEZY_URL_PROMAX = import.meta.env.VITE_LEMON_SQUEEZY_URL_PROMAX || 'https://morelike.lemonsqueezy.com/checkout/buy/81b9a80c-0ac7-491c-aa37-483a0dbda94a'

function Paywall({ onTokenValidated, onCancel }) {
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPlans, setShowPlans] = useState(false)

  const handleValidate = async (e) => {
    e.preventDefault()
    if (!token.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/api/validate-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim() })
      })
      const data = await res.json()
      if (data.valid) {
        onTokenValidated(token.trim(), data.credits, data.email || '', data.plan || 'basic', data.limits || {})
      } else {
        setError('Invalid or expired token.')
      }
    } catch {
      setError('Cannot reach server.')
    }
    setLoading(false)
  }

  return (
    <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-6 md:p-8 border border-yellow-500/30">
      <div className="text-center mb-6">
        <div className="text-4xl mb-3">&#128274;</div>
        <h2 className="text-xl font-bold mb-2">Unlock Your Script Package</h2>
        <p className="text-purple-200 text-sm">
          Analysis is free. Unlock 3 script packages to get started.
        </p>
      </div>

      {!showPlans ? (
        <button
          onClick={() => setShowPlans(true)}
          className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 shadow-lg text-lg"
        >
          Our Plans
        </button>
      ) : (
        <div className="space-y-3 mb-6">
          <div className="flex flex-col sm:flex-row gap-3">
            <a
              href={LEMON_SQUEEZY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 text-center"
            >
              <span className="block text-lg">Basic — $8</span>
              <span className="block text-xs text-purple-200 mt-2">3 min max per video</span>
              <span className="block text-xs text-purple-200">Analyze up to 3 videos</span>
              <span className="block text-xs text-purple-200">Full script + image + video prompts</span>
              <span className="block text-xs text-purple-200">Thumbnail A/B + voice direction</span>
            </a>
            <a
              href={LEMON_SQUEEZY_URL_PRO}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-4 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 text-center"
            >
              <span className="block text-lg">Pro — $10</span>
              <span className="block text-xs text-pink-200 mt-2">5 min max per video</span>
              <span className="block text-xs text-pink-200">Analyze up to 5 videos</span>
              <span className="block text-xs text-pink-200">Full script + image + video prompts</span>
              <span className="block text-xs text-pink-200">Thumbnail A/B + voice direction</span>
            </a>
            <a
              href={LEMON_SQUEEZY_URL_PROMAX}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-4 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 text-center"
            >
              <span className="block text-lg">Pro Max — $15</span>
              <span className="block text-xs text-amber-200 mt-2">15 min max per video</span>
              <span className="block text-xs text-amber-200">Analyze up to 5 videos</span>
              <span className="block text-xs text-amber-200">5 credits (5 script packages)</span>
              <span className="block text-xs text-amber-200">5 title ideas + full prompts</span>
            </a>
          </div>
          <button
            onClick={() => setShowPlans(false)}
            className="w-full py-2 text-gray-400 hover:text-white text-sm transition-colors"
          >
            Hide plans
          </button>
        </div>
      )}

      <div className="border-t border-gray-700 pt-6">
        <p className="text-sm text-gray-400 mb-4 text-center">Already paid? Enter your token:</p>
        <form onSubmit={handleValidate} className="flex gap-2">
          <input
            type="text"
            placeholder="Paste your access token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="flex-1 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
            autoFocus
          />
          <button
            type="submit"
            disabled={loading || !token.trim()}
            className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all disabled:opacity-50 whitespace-nowrap text-sm"
          >
            {loading ? '...' : 'Go'}
          </button>
        </form>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </div>

      <button
        onClick={onCancel}
        className="mt-4 w-full py-2 bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded-lg transition-all text-sm"
      >
        Back to titles
      </button>
    </div>
  )
}

/* ── Structured result renderer ──────────────────────────────── */
/* ── Thumbnail section parser ────────────────────────────────── */
function extractThumbnailSection(packageText) {
  if (!packageText) return ''
  const patterns = [
    /(═+[\s]*THUMBNAIL DESIGN[\s\S]*?)(?=═+[\s]*(?:BEATS|CINEMATIC TIMELINE|INTERNAL REVIEW)|$)/,
    /(═══+[\s]*THUMBNAIL DESIGN[\s\S]*?)(?=═══+[\s]*(?:BEATS|CINEMATIC TIMELINE|INTERNAL REVIEW)|$)/,
  ]
  for (const p of patterns) {
    const m = packageText.match(p)
    if (m) return m[1].trim()
  }
  return ''
}

/* ── Thumbnail Card ──────────────────────────────────────────── */
function ThumbnailCard({ thumbnailSection, regensRemaining, onRegenerate, loading, plan }) {
  if (!thumbnailSection || plan === 'basic') return null

  const canRegen = regensRemaining > 0 && !loading

  return (
    <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-amber-500/30 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-amber-400 rounded-full" />
          <span className="text-amber-400 font-semibold text-sm uppercase tracking-wide">Thumbnail Design</span>
        </div>
        {plan !== 'basic' && (
          <div className="flex items-center gap-2">
            {regensRemaining > 0 && (
              <span className="text-xs text-gray-400">
                {regensRemaining === 9999 ? 'Unlimited regenerations' : `${regensRemaining} regeneration${regensRemaining !== 1 ? 's' : ''} left`}
              </span>
            )}
            <button
              onClick={onRegenerate}
              disabled={!canRegen}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                canRegen
                  ? 'bg-amber-600 hover:bg-amber-700 text-white'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed'
              }`}
            >
              {loading ? 'Regenerating...' : regensRemaining === 0 ? 'No Regens Left' : 'Regenerate'}
            </button>
          </div>
        )}
      </div>

      <pre className="bg-gray-900/70 border border-gray-700 rounded-lg p-4 text-gray-300 text-xs md:text-sm whitespace-pre-wrap font-mono max-h-[40vh] overflow-y-auto leading-relaxed">
        {thumbnailSection}
      </pre>
    </div>
  )
}

function ResultView({ content, title, onDownload, onCopy, creditsAfter }) {
  return (
    <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-green-500/30">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-3 h-3 bg-green-400 rounded-full" />
        <span className="text-green-400 font-semibold">Ready!</span>
      </div>
      <h2 className="text-xl font-bold mb-1">{title}</h2>
      {creditsAfter !== undefined && (
        <p className="text-sm text-gray-400 mb-4">Credits remaining: <strong className="text-white">{creditsAfter}</strong></p>
      )}

      <pre className="bg-gray-900/70 border border-gray-700 rounded-lg p-4 md:p-6 text-gray-300 text-xs md:text-sm whitespace-pre-wrap font-mono max-h-[60vh] overflow-y-auto mb-6 leading-relaxed">
        {content}
      </pre>

      <div className="flex flex-col sm:flex-row gap-2 md:gap-3">
        <button onClick={onDownload} className="px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white font-bold rounded-lg transition-all">
          Download PDF
        </button>
        <button onClick={onCopy} className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
          Copy All
        </button>
      </div>
    </div>
  )
}

/* ── Main Portal ────────────────────────────────────────────── */
function Portal() {
  // Auth
  const [token, setToken] = useState('')
  const [credits, setCredits] = useState(0)
  const [tokenEmail, setTokenEmail] = useState('')
  const [tokenPlan, setTokenPlan] = useState('basic')
  const [planLimits, setPlanLimits] = useState({ max_videos: 3, max_minutes: 3 })
  const [tokenValidated, setTokenValidated] = useState(false)
  const [showLogin, setShowLogin] = useState(false)

  // Flow state: 'input' | 'processing' | 'manual_transcripts' | 'pick_title' | 'paywall' | 'visual_upload' | 'thumbnail_upload' | 'duration_pick' | 'generating' | 'result'
  const [flow, setFlow] = useState('input')
  const [inputMode, setInputMode] = useState('scrape')
  const [genPercent, setGenPercent] = useState(0)
  const [genStep, setGenStep] = useState('')
  const [durationMinutes, setDurationMinutes] = useState('')
  const [durationSeconds, setDurationSeconds] = useState('')
  const [durationError, setDurationError] = useState('')

  // Pipeline
  const extractLimit = planLimits.max_videos || 3
  const [channelUrl, setChannelUrl] = useState('')
  const [videoMeta, setVideoMeta] = useState([])  // For manual transcript fallback
  const [manualTranscripts, setManualTranscripts] = useState({})
  const [videoLength, setVideoLength] = useState(3)
  const [userVideoIdea, setUserVideoIdea] = useState('')
  const [pastedScript, setPastedScript] = useState('')
  const [viralDNA, setViralDNA] = useState('')
  const [titles, setTitles] = useState('')
  const [parsedTitles, setParsedTitles] = useState([])
  const [chosenTitle, setChosenTitle] = useState('')
  const [finalPackage, setFinalPackage] = useState('')
  const [creditsAfter, setCreditsAfter] = useState(0)
  const [pipelineError, setPipelineError] = useState('')
  const [currentJobId, setCurrentJobId] = useState('')
  const [thumbnailRegens, setThumbnailRegens] = useState(0)
  const [regenLoading, setRegenLoading] = useState(false)

  // Per-video extraction status
  const [extractionVideos, setExtractionVideos] = useState([])

  // Pending title (held during paywall)
  const pendingTitle = useRef('')
  const pendingTopic = useRef('')

  // Visual analysis
  const [visualImages, setVisualImages] = useState([])
  const [thumbnailImages, setThumbnailImages] = useState([])
  const [visualProfile, setVisualProfile] = useState(null)
  const [thumbnailProfile, setThumbnailProfile] = useState(null)
  const visualProfileRef = useRef(null)
  const thumbnailProfileRef = useRef(null)

  // Feedback
  const [feedbackMsg, setFeedbackMsg] = useState('')
  const [feedbackSent, setFeedbackSent] = useState(false)

  const extractedRef = useRef('')
  const extractedVideoIdsRef = useRef([])
  const inputModeRef = useRef('scrape')
  const extractTimeoutRef = useRef(null)

  // ── Auto-login from sessionStorage ─────────────────────────────
  useEffect(() => {
    const stored = sessionStorage.getItem('morelike_token')
    const storedCreds = sessionStorage.getItem('morelike_credits')
    if (stored && storedCreds && parseInt(storedCreds) > 0) {
      fetch(`${API_URL}/api/validate-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: stored.trim() })
      }).then(r => r.json()).then(data => {
        if (data.valid && data.credits > 0) {
          setToken(stored)
          setCredits(data.credits)
          setTokenEmail(data.email || '')
          setTokenPlan(data.plan || 'basic')
          setPlanLimits(data.limits || { max_videos: 3, max_minutes: 3 })
          setTokenValidated(true)
          setVideoLength(data.limits?.max_minutes || 3)
        } else {
          sessionStorage.removeItem('morelike_token')
          sessionStorage.removeItem('morelike_credits')
          sessionStorage.removeItem('morelike_plan')
        }
      }).catch(() => { })
    }
  }, [])

  // ── Token validation ────────────────────────────────────────
  const handleValidateToken = async (e) => {
    e.preventDefault()
    try {
      const res = await fetch(`${API_URL}/api/validate-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim() })
      })
      const data = await res.json()
      if (data.valid) {
        setCredits(data.credits)
        setTokenEmail(data.email || '')
        setTokenPlan(data.plan || 'basic')
        setPlanLimits(data.limits || { max_videos: 3, max_minutes: 3 })
        setTokenValidated(true)
        setShowLogin(false)
        setVideoLength(data.limits?.max_minutes || 3)
        sessionStorage.setItem('morelike_token', token.trim())
        sessionStorage.setItem('morelike_credits', String(data.credits))
        sessionStorage.setItem('morelike_plan', data.plan || 'basic')
      } else {
        alert('Invalid or expired token.')
      }
    } catch {
      alert('Cannot reach server.')
    }
  }

  // ── Paywall callback ────────────────────────────────────────
  const handlePaywallValidated = useCallback((validatedToken, creds, email, plan, limits) => {
    setToken(validatedToken)
    setCredits(creds)
    setTokenEmail(email)
    setTokenPlan(plan || 'basic')
    setPlanLimits(limits || { max_videos: 3, max_minutes: 3 })
    setTokenValidated(true)
    setVideoLength(limits?.max_minutes || 3)
    sessionStorage.setItem('morelike_token', validatedToken)
    sessionStorage.setItem('morelike_credits', String(creds))
    sessionStorage.setItem('morelike_plan', plan || 'basic')
    setFlow('visual_upload')
  }, [])

  // ── AI fetch helper ─────────────────────────────────────────
  const aiFetch = useCallback(async (url, body) => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 180000)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify(body),
        signal: controller.signal
      })
      clearTimeout(timer)
      return res
    } catch (e) {
      clearTimeout(timer)
      throw e
    }
  }, [token])

  // ── Generate package (async: starts job, polls until complete) ──
  const doGeneratePackage = useCallback(async (authToken, title, customTopic, visProfile, thumbProfile) => {
    const authHeader = authToken ? getApiHeaders(authToken) : getApiHeaders(token)

    try {
      // Step 1: Start generation job
      const res = await fetch(`${API_URL}/api/generate-package`, {
        method: 'POST',
        headers: authHeader,
        body: JSON.stringify({
          viral_dna: viralDNA,
          title,
          topic: customTopic || '',
          video_length: videoLength,
          visual_json: visProfile || null,
          thumbnail_json: thumbProfile || null,
          transcript_context: extractedRef.current || ''
        }),
        signal: (() => { const c = new AbortController(); setTimeout(() => c.abort(), 30000); return c.signal })()
      })
      const data = await res.json()

      if (res.status === 401 || res.status === 402) {
        setTokenValidated(false)
        setToken('')
        sessionStorage.removeItem('morelike_token')
        sessionStorage.removeItem('morelike_credits')
        setFlow('paywall')
        alert(data.error || 'Token expired or no credits.')
        return
      }

      if (!data.success || !data.job_id) {
        alert(data.error || 'Failed to start generation')
        setFlow('pick_title')
        return
      }

      // Step 2: Poll for completion with progress updates
      const jobId = data.job_id
      let attempts = 0
      const maxAttempts = 120  // 120 × 2s = 4 minutes max

      while (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 1500))
        attempts++

        try {
          const pollRes = await fetch(`${API_URL}/api/generation-status/${jobId}`, {
            headers: authHeader,
            signal: (() => { const c = new AbortController(); setTimeout(() => c.abort(), 10000); return c.signal })()
          })

          if (!pollRes.ok && pollRes.status !== 500) continue

          const pollData = await pollRes.json()

          // Update progress display
          setGenPercent(pollData.percent || 0)
          setGenStep(pollData.step || '')

          if (pollData.status === 'complete') {
            setFinalPackage(pollData.package)
            setCreditsAfter(pollData.credits_remaining)
            setCredits(pollData.credits_remaining)
            setCurrentJobId(pollData.job_id || jobId)
            setThumbnailRegens(pollData.thumbnail_regens_remaining || 0)
            setTokenPlan(pollData.plan || tokenPlan)
            sessionStorage.setItem('morelike_credits', String(pollData.credits_remaining))
            setFlow('result')
            return
          }

          if (pollData.status === 'error') {
            alert(pollData.error || 'Generation failed')
            setFlow('pick_title')
            return
          }
        } catch {
          // Poll request failed, keep trying
        }
      }

      // Timed out after maxAttempts
      alert('Generation is taking longer than expected. Please wait — your package will appear when ready. You can also try refreshing.')
      setFlow('pick_title')
    } catch {
      alert('Failed to reach server')
      setFlow('pick_title')
    }
  }, [viralDNA, videoLength, token])

  // ── Automated pipeline ──────────────────────────────────────
  const runPipeline = useCallback(async (extractedText) => {
    try {
      const dnaRes = await aiFetch(`${API_URL}/api/generate-viral-dna`, { subtitles: extractedText })
      const dnaData = await dnaRes.json()
      if (!dnaData.success) throw new Error(dnaData.error || 'Analysis failed')
      setViralDNA(dnaData.viral_dna)

      const titlesRes = await aiFetch(`${API_URL}/api/generate-titles`, { viral_dna: dnaData.viral_dna, count: tokenPlan === 'promax' ? 5 : 3 })
      const titlesData = await titlesRes.json()
      if (!titlesData.success) throw new Error(titlesData.error || 'Title generation failed')
      setTitles(titlesData.titles)
      const lines = titlesData.titles.split('\n').filter((l) => /^\d+[\.\)]/.test(l.trim()))
      setParsedTitles(lines.map((l) => l.replace(/^\d+[\.\)]\s*/, '').trim()))

      setTimeout(() => setFlow('pick_title'), 600)
    } catch (err) {
      setPipelineError(err.message)
      setFlow('input')
    }
  }, [aiFetch])

  // ── Idea mode: resolve channel → paste channel transcripts → generate titles ──
  const handleIdeaAndGo = async () => {
    if (!userVideoIdea.trim() || !channelUrl.trim()) return
    setPipelineError('')
    inputModeRef.current = 'idea'
    pendingTopic.current = userVideoIdea.trim()
    setExtractionVideos([])
    setPastedScript('')
    setFlow('processing')

    try {
      const res = await fetch(`${API_URL}/api/channel-videos`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ channel_url: channelUrl.trim(), limit: extractLimit }),
        signal: (() => { const c = new AbortController(); setTimeout(() => c.abort(), 30000); return c.signal })()
      })
      const data = await res.json()

      if (!res.ok || data.error) {
        setPipelineError(data.error || 'Could not reach server. Check your channel URL.')
        setFlow('input')
        return
      }

      const videos = data.video_meta || []
      setExtractionVideos(videos.map(v => ({ title: v.title, status: 'done' })))
      setVideoMeta(videos)
      setManualTranscripts({})

      if (data.warning) setPipelineError(data.warning)
      setTimeout(() => setFlow('manual_transcripts'), videos.length ? 1200 : 400)
    } catch {
      setPipelineError('Could not fetch video list.')
      setVideoMeta([])
      setManualTranscripts({})
      setTimeout(() => setFlow('manual_transcripts'), 600)
    }
  }

  // ── Start extraction → always go to manual transcript paste ────
  const handleStart = async () => {
    if (!channelUrl.trim()) return
    setPipelineError('')
    inputModeRef.current = 'scrape'
    setExtractionVideos([])
    setPastedScript('')
    setFlow('processing')

    try {
      const res = await fetch(`${API_URL}/api/channel-videos`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ channel_url: channelUrl.trim(), limit: extractLimit }),
        signal: (() => { const c = new AbortController(); setTimeout(() => c.abort(), 30000); return c.signal })()
      })
      const data = await res.json()

      if (!res.ok || data.error) {
        setPipelineError(data.error || 'Could not reach server. Check your channel URL.')
        setFlow('input')
        return
      }

      const videos = data.video_meta || []
      setExtractionVideos(videos.map(v => ({ title: v.title, status: 'done' })))
      setVideoMeta(videos)
      setManualTranscripts({})

      if (data.warning) setPipelineError(data.warning)
      setTimeout(() => setFlow('manual_transcripts'), videos.length ? 1200 : 400)
    } catch {
      setPipelineError('Could not fetch video list — you can still paste transcripts below.')
      setVideoMeta([])
      setManualTranscripts({})
      setTimeout(() => setFlow('manual_transcripts'), 600)
    }
  }

  // ── Title chosen ────────────────────────────────────────────
  const handleChooseTitle = (title, customTopic) => {
    setChosenTitle(title)

    if (tokenValidated && credits > 0) {
      // Authenticated — go to visual upload first
      pendingTitle.current = title
      pendingTopic.current = customTopic || pendingTopic.current
      setFlow('visual_upload')
    } else {
      // Hold title and show paywall
      pendingTitle.current = title
      pendingTopic.current = customTopic || pendingTopic.current
      setFlow('paywall')
    }
  }

  // ── Regenerate titles ───────────────────────────────────────
  const handleRegenerateTitles = async () => {
    setFlow('processing')
    try {
      const res = await aiFetch(`${API_URL}/api/generate-titles`, { viral_dna: viralDNA, count: tokenPlan === 'promax' ? 5 : 3, topic: pendingTopic.current })
      const data = await res.json()
      if (data.success) {
        setTitles(data.titles)
        const lines = data.titles.split('\n').filter((l) => /^\d+[\.\)]/.test(l.trim()))
        setParsedTitles(lines.map((l) => l.replace(/^\d+[\.\)]\s*/, '').trim()))
        setFlow('pick_title')
      } else {
        throw new Error(data.error)
      }
    } catch {
      alert('Failed to regenerate titles')
      setFlow('pick_title')
    }
  }

  // ── Download ────────────────────────────────────────────────
  const handleDownload = async () => {
    try {
      const jobParam = currentJobId ? `?job_id=${encodeURIComponent(currentJobId)}` : ''
      const res = await fetch(`${API_URL}/api/download-package${jobParam}`, {
        headers: getApiHeaders(token)
      })
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${chosenTitle.slice(0, 40).replace(/[\/:*?"<>|]/g, '-')}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        // Server failed — generate PDF client-side
        const doc = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
        doc.setFont('Helvetica', 'normal')
        doc.setFontSize(8)
        const margins = { top: 12, bottom: 12, left: 12, right: 12 }
        const pageWidth = doc.internal.pageSize.getWidth()
        const maxWidth = pageWidth - margins.left - margins.right
        const lineHeight = 4.0
        let y = margins.top
        const lines = finalPackage.split('\n')
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) {
            y += lineHeight
            continue
          }
          const safe = trimmed.replace(/[^\x20-\x7E -ÿ]/g, '')
          const wrapped = doc.splitTextToSize(safe, maxWidth)
          for (const wLine of wrapped) {
            if (y + lineHeight > doc.internal.pageSize.getHeight() - margins.bottom) {
              doc.addPage()
              y = margins.top
            }
            doc.text(wLine, margins.left, y)
            y += lineHeight
          }
        }
        const pdfBlob = doc.output('blob')
        const url = URL.createObjectURL(pdfBlob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${chosenTitle.slice(0, 40).replace(/[\/:*?"<>|]/g, '-')}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch {
      alert('Failed to download')
    }
  }

  // ── Thumbnail Regeneration ───────────────────────────────────
  const handleRegenerateThumbnail = async () => {
    if (!currentJobId || thumbnailRegens <= 0) return
    setRegenLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/regenerate-thumbnail`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ job_id: currentJobId })
      })
      const data = await res.json()

      if (!res.ok) {
        alert(data.error || 'Regeneration failed')
        return
      }

      if (data.success && data.thumbnail_section) {
        // Replace the thumbnail section in the full package
        const oldSection = extractThumbnailSection(finalPackage)
        let updatedPackage = finalPackage
        if (oldSection) {
          updatedPackage = finalPackage.replace(oldSection, data.thumbnail_section)
        }
        setFinalPackage(updatedPackage)
        setThumbnailRegens(data.regenerations_remaining)
      }
    } catch {
      alert('Failed to reach server for regeneration')
    } finally {
      setRegenLoading(false)
    }
  }

  // ── Feedback ────────────────────────────────────────────────
  const handleFeedback = async () => {
    if (!feedbackMsg.trim()) return
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 15000)
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ message: feedbackMsg }),
        signal: ctrl.signal
      })
      setFeedbackSent(true)
    } catch {
      alert('Failed to send feedback. Please try again.')
    } finally {
      clearTimeout(timer)
    }
  }

  // ── Visual upload handlers ──────────────────────────────────
  const handleVisualUpload = async () => {
    if (visualImages.length < 3) {
      alert('Please upload at least 3 reference images from the channel videos.')
      return
    }
    setFlow('processing')
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 120000)
    try {
      const form = new FormData()
      visualImages.forEach((f) => form.append('images', f))
      const res = await fetch(`${API_URL}/api/analyze-visuals`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
        signal: ctrl.signal
      })
      const data = await res.json()
      if (data.success) {
        setVisualProfile(data.visual_profile)
        visualProfileRef.current = data.visual_profile
        setFlow('thumbnail_upload')
      } else {
        throw new Error(data.error)
      }
    } catch (e) {
      alert('Visual analysis failed: ' + (e.message || 'Server error'))
      setFlow('visual_upload')
    } finally {
      clearTimeout(timer)
    }
  }

  const handleThumbnailUpload = async () => {
    if (thumbnailImages.length < 2) {
      alert('Please upload at least 2 thumbnail reference images from the channel.')
      return
    }
    setFlow('processing')
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 120000)
    try {
      const form = new FormData()
      thumbnailImages.forEach((f) => form.append('images', f))
      const res = await fetch(`${API_URL}/api/analyze-thumbnails`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
        signal: ctrl.signal
      })
      const data = await res.json()
      if (data.success) {
        setThumbnailProfile(data.thumbnail_profile)
        thumbnailProfileRef.current = data.thumbnail_profile
        if (tokenPlan === 'basic') {
          setFlow('generating')
          setGenPercent(0)
          setGenStep('')
          doGeneratePackage(token, pendingTitle.current, pendingTopic.current, visualProfileRef.current, data.thumbnail_profile)
        } else {
          // Pro / Pro Max — let user pick duration
          const maxMin = planLimits.max_minutes || 5
          setDurationMinutes(String(Math.min(3, maxMin)))
          setDurationSeconds('00')
          setDurationError('')
          setFlow('duration_pick')
        }
      } else {
        throw new Error(data.error)
      }
    } catch (e) {
      alert('Thumbnail analysis failed: ' + (e.message || 'Server error'))
      setFlow('thumbnail_upload')
    } finally {
      clearTimeout(timer)
    }
  }

  const handleAutoThumbnail = async (authToken, visProfile) => {
    const vids = extractedVideoIdsRef.current
    if (!vids.length || vids.length < 2) {
      setFlow('thumbnail_upload')
      return
    }
    setFlow('processing')
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60000)
    try {
      const res = await fetch(`${API_URL}/api/analyze-thumbnails-auto`, {
        method: 'POST',
        headers: { ...getApiHeaders(authToken), 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: vids }),
        signal: ctrl.signal
      })
      const data = await res.json()
      if (data.success) {
        setThumbnailProfile(data.thumbnail_profile)
        thumbnailProfileRef.current = data.thumbnail_profile
        if (tokenPlan === 'basic') {
          setFlow('generating')
          setGenPercent(0)
          setGenStep('')
          doGeneratePackage(authToken, pendingTitle.current, pendingTopic.current, visProfile, data.thumbnail_profile)
        } else {
          const maxMin = planLimits.max_minutes || 5
          setDurationMinutes(String(Math.min(3, maxMin)))
          setDurationSeconds('00')
          setDurationError('')
          setFlow('duration_pick')
        }
      } else {
        setFlow('thumbnail_upload')
      }
    } catch {
      setFlow('thumbnail_upload')
    } finally {
      clearTimeout(timer)
    }
  }

  const handleRemoveVisualImage = (index) => {
    setVisualImages((prev) => prev.filter((_, i) => i !== index))
  }

  const handleRemoveThumbnailImage = (index) => {
    setThumbnailImages((prev) => prev.filter((_, i) => i !== index))
  }

  // ── Manual transcript submit ──────────────────────────────────
  const handleManualSubmit = async () => {
    setFlow('processing')
    try {
      if (inputModeRef.current === 'idea') {
        // Idea mode: channel transcripts → DNA → titles from (DNA + user's video idea)
        const videoIdea = pendingTopic.current || userVideoIdea.trim()
        if (!videoIdea) {
          setPipelineError('Please enter your video idea first.')
          setFlow('input')
          return
        }

        // Build transcript content from channel videos (style reference only, no user script)
        let transcriptContent = ''
        const channelTexts = Object.values(manualTranscripts).filter(t => t.trim().length > 20)
        if (channelTexts.length > 0) {
          transcriptContent += '=== CHANNEL STYLE REFERENCE TRANSCRIPTS ===\n\n'
          for (const [vId, text] of Object.entries(manualTranscripts)) {
            if (text.trim().length > 20) {
              const meta = videoMeta.find(v => v.id === vId)
              transcriptContent += '### ' + (meta ? meta.title : 'Video') + ' ###\n' + text.trim() + '\n\n'
            }
          }
        }

        if (!transcriptContent.trim()) {
          setPipelineError('Please paste at least one channel transcript for style reference.')
          setFlow('manual_transcripts')
          return
        }

        extractedRef.current = transcriptContent

        // Generate Viral DNA from channel transcripts
        const dnaRes = await aiFetch(`${API_URL}/api/generate-viral-dna`, { subtitles: transcriptContent })
        const dnaData = await dnaRes.json()
        if (!dnaData.success) {
          setPipelineError(dnaData.error || 'Style analysis failed')
          setFlow('manual_transcripts')
          return
        }
        setViralDNA(dnaData.viral_dna)

        // Generate 5 titles from DNA + user's video idea
        const titlesRes = await aiFetch(`${API_URL}/api/generate-titles`, {
          viral_dna: dnaData.viral_dna,
          count: 5,
          topic: videoIdea
        })
        const titlesData = await titlesRes.json()
        if (!titlesData.success) throw new Error(titlesData.error || 'Title generation failed')
        setTitles(titlesData.titles)
        const lines = titlesData.titles.split('\n').filter((l) => /^\d+[\.\)]/.test(l.trim()))
        setParsedTitles(lines.map((l) => l.replace(/^\d+[\.\)]\s*/, '').trim()))

        setTimeout(() => setFlow('pick_title'), 600)
      } else {
        // Scrape mode: use channel transcripts
        const res = await fetch(`${API_URL}/api/manual-transcripts`, {
          method: 'POST',
          headers: getApiHeaders(token),
          body: JSON.stringify({ transcripts: manualTranscripts, video_meta: videoMeta })
        })
        const data = await res.json()
        if (data.success) {
          const subRes = await fetch(`${API_URL}/api/subtitles`, { headers: getApiHeaders(token) })
          const subData = await subRes.json()
          if (subData.content) {
            extractedRef.current = subData.content
            extractedVideoIdsRef.current = subData.video_ids || []
            runPipeline(subData.content)
          }
        } else {
          setPipelineError(data.error || 'Failed to process transcripts')
          setFlow('manual_transcripts')
        }
      }
    } catch {
      setPipelineError('Failed to reach server')
      setFlow('manual_transcripts')
    }
  }

  // ── Duration confirm (Pro / Pro Max plans) ─────────────────
  const handleDurationConfirm = () => {
    const mins = parseInt(durationMinutes, 10)
    const secs = parseInt(durationSeconds, 10)
    if (isNaN(mins) || isNaN(secs) || mins < 0 || secs < 0 || secs > 59) {
      setDurationError('Enter a valid time, e.g. 02:30')
      return
    }
    const totalMinutes = mins + (secs / 60)
    if (totalMinutes <= 0) {
      setDurationError('Duration must be at least 1 second')
      return
    }
    const maxMin = planLimits.max_minutes || 5
    if (totalMinutes > maxMin) {
      setDurationError(`Max ${maxMin} min for ${tokenPlan === 'promax' ? 'Pro Max' : 'Pro'} plan`)
      return
    }
    setVideoLength(totalMinutes)
    setFlow('generating')
    setGenPercent(0)
    setGenStep('')
    doGeneratePackage(token, pendingTitle.current, pendingTopic.current, visualProfileRef.current, thumbnailProfileRef.current)
  }

  // ── Reset ───────────────────────────────────────────────────
  const handleReset = () => {
    setFlow('input')
    setChannelUrl('')
    setUserVideoIdea('')
    inputModeRef.current = 'scrape'
    setViralDNA('')
    setTitles('')
    setParsedTitles([])
    setChosenTitle('')
    setFinalPackage('')
    setPipelineError('')
    setExtractionVideos([])
    setVideoMeta([])
    setManualTranscripts({})
    setFeedbackMsg('')
    setVisualImages([])
    setThumbnailImages([])
    setVisualProfile(null)
    setThumbnailProfile(null)
    visualProfileRef.current = null
    thumbnailProfileRef.current = null
    setFeedbackSent(false)
    extractedRef.current = ''
    extractedVideoIdsRef.current = []
    pendingTitle.current = ''
    pendingTopic.current = ''
    setGenPercent(0)
    setGenStep('')
    setDurationMinutes('')
    setDurationSeconds('')
    setDurationError('')
    setPastedScript('')
    setCurrentJobId('')
    setThumbnailRegens(0)
    setRegenLoading(false)
  }

  // Logout
  const handleLogout = () => {
    setToken('')
    setCredits(0)
    setTokenEmail('')
    setTokenPlan('basic')
    setPlanLimits({ max_videos: 3, max_minutes: 3 })
    setTokenValidated(false)
    sessionStorage.removeItem('morelike_token')
    sessionStorage.removeItem('morelike_credits')
    sessionStorage.removeItem('morelike_plan')
  }

  // ── BG BLOBS ────────────────────────────────────────────────
  const bgBlobs = (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '2s' }} />
    </div>
  )

  // ── HEADER ──────────────────────────────────────────────────
  const header = (
    <div className="flex justify-between items-center mb-6 md:mb-8 flex-wrap gap-3">
      <div className="flex items-center gap-2 md:gap-3">
        <img
          src="/logo.png" alt="Morelike"
          className="w-8 h-8 md:w-10 md:h-10 rounded-xl object-cover"
          onError={(e) => {
            e.target.style.display = 'none'
            e.target.nextSibling.style.display = 'flex'
          }}
        />
        <div className="w-8 h-8 md:w-10 md:h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center font-extrabold text-white text-base md:text-lg shadow-lg shadow-purple-500/30" style={{ display: 'none' }}>M</div>
        <Link to="/" className="text-xl md:text-2xl font-extrabold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight hover:opacity-80 transition-opacity">Morelike</Link>
      </div>
      <div className="flex items-center gap-3 md:gap-4 flex-wrap">
        {tokenValidated ? (
          <>
            <span className="text-xs md:text-sm text-gray-400">{tokenEmail && `${tokenEmail} | `}{tokenPlan === 'promax' ? 'Pro Max' : tokenPlan === 'pro' ? 'Pro' : 'Basic'} · Credits: <strong className="text-white">{credits}</strong></span>
            <button onClick={handleLogout} className="text-xs md:text-sm text-gray-400 hover:text-white transition-colors">Logout</button>
          </>
        ) : (
          <button onClick={() => setShowLogin(!showLogin)} className="text-xs md:text-sm text-purple-400 hover:text-purple-300 transition-colors">
            Already have a token?
          </button>
        )}
        <Link to="/" className="text-xs md:text-sm text-gray-400 hover:text-white transition-colors">Home</Link>
      </div>
    </div>
  )

  // ── TOKEN LOGIN DROPDOWN ────────────────────────────────────
  const tokenLoginInline = showLogin && !tokenValidated && (
    <div className="bg-gray-800/80 backdrop-blur-lg rounded-xl border border-purple-500/30 p-4 mb-6">
      <form onSubmit={handleValidateToken} className="flex gap-2">
        <input
          type="text"
          placeholder="Paste your access token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="flex-1 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
          autoFocus
        />
        <button
          type="submit"
          className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all text-sm whitespace-nowrap"
        >
          Login
        </button>
      </form>
    </div>
  )

  // ── RENDER ──────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white relative overflow-hidden">
      {bgBlobs}
      <div className="relative z-10 container mx-auto px-4 py-8 max-w-3xl">
        {header}
        {tokenLoginInline}

        {/* ── INPUT SCREEN ──────────────────────────────────── */}
        {flow === 'input' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30">
            <h2 className="text-xl md:text-2xl font-bold mb-2">Generate Content Ideas</h2>
            <p className="text-purple-200 mb-6">Paste a YouTube channel you admire. We'll reverse-engineer what works and give you fresh ideas — free.</p>

            <div className="flex gap-2 mb-6">
              <button onClick={() => setInputMode('scrape')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${inputMode === 'scrape' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                From YouTube
              </button>
              <button onClick={() => setInputMode('idea')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${inputMode === 'idea' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                I have my Video Idea
              </button>
            </div>

            {pipelineError && (
              <div className="mb-4 p-3 bg-red-900/20 border border-red-500/50 rounded-lg text-red-400 text-sm">{pipelineError}</div>
            )}

            {inputMode === 'scrape' && (
              <>
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">YouTube Channel URL</label>
                    <input
                      type="text"
                      placeholder="https://www.youtube.com/@ChannelName"
                      value={channelUrl}
                      onChange={(e) => setChannelUrl(e.target.value)}
                      className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                </div>
                <button
                  onClick={handleStart}
                  disabled={!channelUrl.trim()}
                  className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
                >
                  Analyze Channel (Free)
                </button>
              </>
            )}

            {inputMode === 'idea' && (
              <>
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">Describe your video idea</label>
                    <textarea
                      placeholder="Describe your video concept, topic, or script outline..."
                      value={userVideoIdea}
                      onChange={(e) => setUserVideoIdea(e.target.value)}
                      className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      rows={6}
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">YouTube Channel for Style Reference</label>
                    <input
                      type="text"
                      placeholder="https://www.youtube.com/@ChannelName"
                      value={channelUrl}
                      onChange={(e) => setChannelUrl(e.target.value)}
                      className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">We'll analyze this channel's style and apply it to your idea.</p>
                  </div>
                </div>
                <button
                  onClick={handleIdeaAndGo}
                  disabled={!userVideoIdea.trim() || !channelUrl.trim()}
                  className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
                >
                  Analyze Channel & Continue (Free)
                </button>
              </>
            )}
          </div>
        )}

        {/* ── PROCESSING SCREEN ─────────────────────────────── */}
        {flow === 'processing' && (
          <div className="relative rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30 text-center overflow-hidden min-h-[300px] md:min-h-[400px] flex flex-col items-center justify-center">
            <div
              className="absolute inset-0 bg-cover bg-center bg-no-repeat"
              style={{ backgroundImage: 'url(/processor.jpg)' }}
            />
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative z-10 w-full max-w-md">
              <h2 className="text-2xl font-bold mb-1 text-white">
                {extractionVideos.length > 0
                  ? `Found ${extractionVideos.length} Video${extractionVideos.length !== 1 ? 's' : ''}`
                  : inputModeRef.current === 'idea' ? 'Analyzing Channel Style' : 'Analyzing Channel'}
              </h2>
              <p className="text-purple-200/50 text-sm mb-4">
                {extractionVideos.length > 0
                  ? 'Switching to transcript paste...'
                  : 'Scanning channel via YouTube API...'}
              </p>
              {extractionVideos.length === 0 && <ProgressBar />}
              {extractionVideos.length > 0 && (
                <div className="w-full max-w-md mx-auto py-4">
                  <div className="w-full h-2 bg-green-500/30 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all duration-500" style={{ width: '100%' }} />
                  </div>
                </div>
              )}

              {extractionVideos.length > 0 && (
                <div className="mt-4 space-y-2 text-left">
                  {extractionVideos.map((vid, i) => (
                    <div key={i} className="flex items-center gap-3 bg-white/5 rounded-lg px-3 py-2">
                      {vid.status === 'extracting' && (
                        <svg className="w-4 h-4 flex-shrink-0 animate-spin text-purple-400" viewBox="0 0 24 24" fill="none">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="50" strokeDashoffset="15" />
                        </svg>
                      )}
                      {vid.status === 'done' && (
                        <svg className="w-4 h-4 flex-shrink-0 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      )}
                      {vid.status === 'failed' && (
                        <svg className="w-4 h-4 flex-shrink-0 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      )}
                      {vid.status === 'pending' && (
                        <div className="w-4 h-4 flex-shrink-0 rounded-full border border-gray-500" />
                      )}
                      <span className={`text-sm truncate ${vid.status === 'done' ? 'text-green-300' :
                          vid.status === 'failed' ? 'text-amber-300' :
                            vid.status === 'extracting' ? 'text-purple-300' :
                              'text-gray-400'
                        }`}>
                        {vid.title || `Video ${i + 1}...`}
                      </span>
                      {vid.status === 'extracting' && (
                        <span className="text-xs text-purple-400/60 ml-auto flex-shrink-0">extracting...</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── MANUAL TRANSCRIPT UPLOAD (scrape mode) ──────── */}
        {flow === 'manual_transcripts' && inputModeRef.current !== 'idea' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-amber-500/30">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-3 h-3 bg-amber-400 rounded-full animate-pulse" />
              <span className="text-amber-400 font-semibold text-sm">Auto-extraction blocked by YouTube</span>
            </div>
            <h2 className="text-xl font-bold mb-2">Paste Transcripts Manually</h2>
            <p className="text-purple-200 text-sm mb-6">
              YouTube blocks automated transcript downloads from cloud servers.
              Please manually copy and paste the transcripts for at least 2 of the top-performing videos below.
              <span className="block mt-2 text-gray-400">How to get transcripts: Open the video on YouTube → click the <strong>••• More</strong> button below the video → <strong>Show transcript</strong> → select all text → paste here.</span>
            </p>

            <div className="space-y-6 mb-6">
              {videoMeta.map((v, i) => (
                <div key={v.id} className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs bg-purple-600 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold">{i + 1}</span>
                    <a href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noopener noreferrer" className="text-white font-semibold hover:text-purple-400 transition-colors text-sm">{v.title}</a>
                  </div>
                  <textarea
                    placeholder={`Paste transcript for "${v.title.slice(0, 40)}..." here...`}
                    value={manualTranscripts[v.id] || ''}
                    onChange={(e) => setManualTranscripts(prev => ({ ...prev, [v.id]: e.target.value }))}
                    className="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                    rows={6}
                  />
                </div>
              ))}
            </div>

            <p className="text-xs text-gray-400 mb-4">
              Transcripts provided: {Object.values(manualTranscripts).filter(t => t.trim().length > 20).length} / {videoMeta.length} (at least 2 needed)
            </p>

            <div className="flex gap-3">
              <button
                onClick={handleManualSubmit}
                disabled={Object.values(manualTranscripts).filter(t => t.trim().length > 20).length < 2}
                className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white font-bold rounded-lg transition-all disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed"
              >
                Analyze Transcripts
              </button>
              <button onClick={() => { setFlow('input'); setPipelineError('') }} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm">
                Try Different Channel
              </button>
            </div>
          </div>
        )}

        {/* ── CHANNEL STYLE REFERENCE (idea mode) ────────── */}
        {flow === 'manual_transcripts' && inputModeRef.current === 'idea' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30">
            <h2 className="text-xl font-bold mb-2">Channel Style Reference</h2>
            <p className="text-purple-200 text-sm mb-2">
              Paste transcripts from the channel's top videos below. We'll analyze their style and generate 5 unique titles based on your idea:
              <span className="text-white font-semibold block mt-1">"{pendingTopic.current || userVideoIdea}"</span>
            </p>

            {/* Channel transcripts — always visible */}
            <div className="space-y-4 mb-6">
              {videoMeta.map((v, i) => (
                <div key={v.id} className="bg-gray-900/50 rounded-lg p-3 border border-gray-700">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs bg-purple-600 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold">{i + 1}</span>
                    <a href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noopener noreferrer" className="text-white text-sm hover:text-purple-400 transition-colors">{v.title}</a>
                  </div>
                  <textarea
                    placeholder="Paste transcript here for style analysis..."
                    value={manualTranscripts[v.id] || ''}
                    onChange={(e) => setManualTranscripts(prev => ({ ...prev, [v.id]: e.target.value }))}
                    className="w-full bg-gray-800/50 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                    rows={5}
                  />
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleManualSubmit}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all"
              >
                Analyze Style & Generate Titles
              </button>
              <button onClick={() => { setFlow('input'); setPipelineError('') }} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm">
                Back
              </button>
            </div>
          </div>
        )}

        {/* ── TITLE PICKER ──────────────────────────────────── */}
        {flow === 'pick_title' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30">
            <TitlePicker
              titles={parsedTitles}
              onChoose={handleChooseTitle}
              onRegenerate={handleRegenerateTitles}
              loading={false}
            />
            <p className="text-gray-500 text-xs mt-4">Selecting a title will prompt you to unlock the full script package — plans start at $8. Basic: 3 min per video &middot; Pro: 5 min &middot; Pro Max: 15 min.</p>
            <button onClick={handleReset} className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all text-sm">
              Start Over
            </button>
          </div>
        )}

        {/* ── PAYWALL ───────────────────────────────────────── */}
        {flow === 'paywall' && (
          <div className="max-w-md mx-auto">
            <Paywall
              onTokenValidated={handlePaywallValidated}
              onCancel={() => setFlow('pick_title')}
            />
          </div>
        )}

        {/* ── VISUAL UPLOAD ─────────────────────────────────── */}
        {flow === 'visual_upload' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30">
            <h2 className="text-xl font-bold mb-1">Upload Reference Images</h2>
            <p className="text-purple-200 text-sm mb-6">
              Upload <strong>3-5 screenshots or stills</strong> from the channel's videos (NOT thumbnails).
              These will be analyzed to match the exact visual style — art style, lighting, composition, color palette.
            </p>

            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files || [])
                if (files.length + visualImages.length > 5) {
                  alert('Maximum 5 images allowed')
                  return
                }
                setVisualImages((prev) => [...prev, ...files].slice(0, 5))
              }}
              className="mb-4 text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-purple-600 file:text-white file:font-semibold hover:file:bg-purple-700"
            />

            {visualImages.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-6">
                {visualImages.map((file, i) => (
                  <div key={i} className="relative group">
                    <img
                      src={URL.createObjectURL(file)}
                      alt={`Ref ${i + 1}`}
                      className="w-full h-24 object-cover rounded-lg border border-gray-600"
                    />
                    <button
                      onClick={() => handleRemoveVisualImage(i)}
                      className="absolute -top-2 -right-2 bg-red-600 text-white w-5 h-5 rounded-full text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      ×
                    </button>
                    <span className="text-xs text-gray-400 block truncate mt-1">{file.name}</span>
                  </div>
                ))}
              </div>
            )}

            <p className="text-gray-400 text-sm mb-4">{visualImages.length} / 5 images selected (minimum 3)</p>

            <div className="flex gap-3">
              <button
                onClick={handleVisualUpload}
                disabled={visualImages.length < 3}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed"
              >
                Analyze Visual Style
              </button>
              <button onClick={() => setFlow('pick_title')} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm">
                Back
              </button>
            </div>
          </div>
        )}

        {/* ── THUMBNAIL UPLOAD ──────────────────────────────── */}
        {flow === 'thumbnail_upload' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30">
            <h2 className="text-xl font-bold mb-1">Upload Thumbnail References</h2>
            <p className="text-purple-200 text-sm mb-6">
              Upload <strong>2-3 thumbnails</strong> from the channel. These are analyzed for text style, composition, color contrast, and emotional triggers.
            </p>

            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files || [])
                if (files.length + thumbnailImages.length > 3) {
                  alert('Maximum 3 thumbnail images allowed')
                  return
                }
                setThumbnailImages((prev) => [...prev, ...files].slice(0, 3))
              }}
              className="mb-4 text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-purple-600 file:text-white file:font-semibold hover:file:bg-purple-700"
            />

            {thumbnailImages.length > 0 && (
              <div className="grid grid-cols-3 gap-3 mb-6">
                {thumbnailImages.map((file, i) => (
                  <div key={i} className="relative group">
                    <img
                      src={URL.createObjectURL(file)}
                      alt={`Thumb ${i + 1}`}
                      className="w-full h-32 object-cover rounded-lg border border-gray-600"
                    />
                    <button
                      onClick={() => handleRemoveThumbnailImage(i)}
                      className="absolute -top-2 -right-2 bg-red-600 text-white w-5 h-5 rounded-full text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      ×
                    </button>
                    <span className="text-xs text-gray-400 block truncate mt-1">{file.name}</span>
                  </div>
                ))}
              </div>
            )}

            <p className="text-gray-400 text-sm mb-4">{thumbnailImages.length} / 3 thumbnails selected (minimum 2)</p>

            <div className="flex gap-3">
              <button
                onClick={handleThumbnailUpload}
                disabled={thumbnailImages.length < 2}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed"
              >
                Analyze Thumbnails & Generate
              </button>
              <button onClick={() => setFlow('visual_upload')} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm">
                Back
              </button>
            </div>
          </div>
        )}

        {/* ── DURATION PICKER (Pro / Pro Max) ──────────────── */}
        {flow === 'duration_pick' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30 max-w-md mx-auto text-center">
            <h2 className="text-xl font-bold mb-1">Choose Video Duration</h2>
            <p className="text-purple-200 text-sm mb-6">
              How long should your video be? (Max {planLimits.max_minutes} min for {tokenPlan === 'promax' ? 'Pro Max' : 'Pro'})
            </p>

            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="flex flex-col items-center">
                <label className="text-xs text-gray-400 mb-1">Minutes</label>
                <input
                  type="number"
                  min="0"
                  max={planLimits.max_minutes}
                  value={durationMinutes}
                  onChange={(e) => { setDurationMinutes(e.target.value); setDurationError('') }}
                  className="w-20 bg-gray-900/80 border border-purple-500/50 rounded-lg px-3 py-3 text-white text-center text-2xl font-bold focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <span className="text-2xl font-bold text-gray-400 mt-5">:</span>
              <div className="flex flex-col items-center">
                <label className="text-xs text-gray-400 mb-1">Seconds</label>
                <input
                  type="number"
                  min="0"
                  max="59"
                  value={durationSeconds}
                  onChange={(e) => { setDurationSeconds(e.target.value.padStart(2, '0')); setDurationError('') }}
                  className="w-20 bg-gray-900/80 border border-purple-500/50 rounded-lg px-3 py-3 text-white text-center text-2xl font-bold focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            {durationError && (
              <p className="text-red-400 text-sm mb-4">{durationError}</p>
            )}

            <div className="flex gap-3 justify-center mt-6">
              <button
                onClick={handleDurationConfirm}
                className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all"
              >
                Generate Package
              </button>
              <button onClick={() => setFlow('thumbnail_upload')} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm">
                Back
              </button>
            </div>
          </div>
        )}

        {/* ── GENERATING SCREEN ─────────────────────────────── */}
        {flow === 'generating' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30 text-center">
            <h2 className="text-xl font-bold mb-2">Creating Your Package</h2>

            {/* Progress bar with percentage */}
            <div className="w-full max-w-md mx-auto mt-6 mb-4">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{genStep || 'Initializing...'}</span>
                <span>{genPercent}%</span>
              </div>
              <div className="relative w-full h-3 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="absolute inset-0 bg-gradient-to-r from-purple-500 via-pink-500 to-amber-400 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(genPercent || 2, 2)}%` }}
                />
              </div>
            </div>

            {/* Progress steps checklist */}
            <div className="max-w-sm mx-auto mt-6 space-y-2 text-left">
              {[
                { label: 'Assemble Viral DNA + visual style', pct: 10 },
                { label: 'Analyze speech patterns', pct: 25 },
                { label: 'Generate script beats + hooks', pct: 40 },
                { label: 'Write voice-over segments', pct: 60 },
                { label: 'Craft image + video prompts', pct: 75 },
                { label: 'Build thumbnail A/B + SEO metadata', pct: 90 },
              ].map((item) => {
                const done = genPercent >= item.pct
                const active = genPercent >= item.pct - 10 && genPercent < item.pct
                return (
                  <div key={item.pct} className="flex items-center gap-3 text-sm">
                    {done ? (
                      <svg className="w-4 h-4 flex-shrink-0 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : active ? (
                      <svg className="w-4 h-4 flex-shrink-0 animate-spin text-purple-400" viewBox="0 0 24 24" fill="none">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="50" strokeDashoffset="15" />
                      </svg>
                    ) : (
                      <div className="w-4 h-4 flex-shrink-0 rounded-full border border-gray-600" />
                    )}
                    <span className={
                      done ? 'text-green-300' :
                      active ? 'text-purple-300' :
                      'text-gray-500'
                    }>{item.label}</span>
                  </div>
                )
              })}
            </div>

            <p className="text-purple-200/40 text-xs mt-6">This may take 1-2 minutes. Your credit has been applied.</p>
          </div>
        )}

        {/* ── RESULT SCREEN ─────────────────────────────────── */}
        {flow === 'result' && (
          <>
            <ThumbnailCard
              thumbnailSection={extractThumbnailSection(finalPackage)}
              regensRemaining={thumbnailRegens}
              onRegenerate={handleRegenerateThumbnail}
              loading={regenLoading}
              plan={tokenPlan}
            />

            <ResultView
              content={finalPackage}
              title={chosenTitle}
              onDownload={handleDownload}
              onCopy={() => navigator.clipboard.writeText(finalPackage)}
              creditsAfter={creditsAfter}
            />

            {/* Feedback */}
            <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30 mt-6">
              <h3 className="text-lg font-semibold mb-2">How was your experience?</h3>
              {feedbackSent ? (
                <p className="text-green-400 text-sm">Thank you! Your feedback has been submitted.</p>
              ) : (
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    placeholder="Share your thoughts..."
                    value={feedbackMsg}
                    onChange={(e) => setFeedbackMsg(e.target.value)}
                    className="flex-1 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                  />
                  <button onClick={handleFeedback} disabled={!feedbackMsg.trim()} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-all disabled:bg-gray-600 disabled:cursor-not-allowed sm:self-start">
                    Send
                  </button>
                </div>
              )}
            </div>

            <button onClick={handleReset} className="mt-6 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all text-sm">
              Create Another
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default Portal
