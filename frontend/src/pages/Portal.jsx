import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import io from 'socket.io-client'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'
const LEMON_SQUEEZY_URL = import.meta.env.VITE_LEMON_SQUEEZY_URL || 'https://store.lemonsqueezy.com/checkout'

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
function Paywall({ onTokenValidated, onCancel }) {
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
        onTokenValidated(token.trim(), data.credits, data.email || '')
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
          Analysis is free. Unlock 3 script packages for <strong>$8</strong> — up to 3 minutes of video each.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <a
          href={LEMON_SQUEEZY_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 text-center text-sm"
        >
          Get Access — $8
        </a>
      </div>

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
          Download .txt
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
  const [tokenValidated, setTokenValidated] = useState(false)
  const [showLogin, setShowLogin] = useState(false)

  // Flow state: 'input' | 'processing' | 'pick_title' | 'paywall' | 'visual_upload' | 'thumbnail_upload' | 'generating' | 'result'
  const [flow, setFlow] = useState('input')
  const [inputMode, setInputMode] = useState('scrape')

  // Pipeline
  const [channelUrl, setChannelUrl] = useState('')
  const [limit, setLimit] = useState(3)
  const [videoLength, setVideoLength] = useState(3)
  const [pastedSubtitles, setPastedSubtitles] = useState('')
  const [viralDNA, setViralDNA] = useState('')
  const [titles, setTitles] = useState('')
  const [parsedTitles, setParsedTitles] = useState([])
  const [chosenTitle, setChosenTitle] = useState('')
  const [finalPackage, setFinalPackage] = useState('')
  const [creditsAfter, setCreditsAfter] = useState(0)
  const [pipelineError, setPipelineError] = useState('')

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

  // Socket ref
  const socketRef = useRef(null)
  const extractedRef = useRef('')

  // ── Auto-login from localStorage ─────────────────────────────
  useEffect(() => {
    const stored = localStorage.getItem('morelike_token')
    const storedCreds = localStorage.getItem('morelike_credits')
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
          setTokenValidated(true)
        } else {
          localStorage.removeItem('morelike_token')
          localStorage.removeItem('morelike_credits')
        }
      }).catch(() => {})
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
        setTokenValidated(true)
        setShowLogin(false)
        localStorage.setItem('morelike_token', token.trim())
        localStorage.setItem('morelike_credits', String(data.credits))
      } else {
        alert('Invalid or expired token.')
      }
    } catch {
      alert('Cannot reach server.')
    }
  }

  // ── Paywall callback ────────────────────────────────────────
  const handlePaywallValidated = useCallback((validatedToken, creds, email) => {
    setToken(validatedToken)
    setCredits(creds)
    setTokenEmail(email)
    setTokenValidated(true)
    localStorage.setItem('morelike_token', validatedToken)
    localStorage.setItem('morelike_credits', String(creds))
    // Route to visual upload instead of directly generating
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

  // ── Generate package (called after credit check) ────────────
  const doGeneratePackage = useCallback(async (authToken, title, customTopic, visProfile, thumbProfile) => {
    try {
      const res = await fetch(`${API_URL}/api/generate-package`, {
        method: 'POST',
        headers: authToken ? getApiHeaders(authToken) : getApiHeaders(token),
        body: JSON.stringify({
          viral_dna: viralDNA,
          title,
          topic: customTopic || '',
          video_length: videoLength,
          visual_json: visProfile || null,
          thumbnail_json: thumbProfile || null
        }),
        signal: (() => {
          const ctrl = new AbortController()
          setTimeout(() => ctrl.abort(), 180000)
          return ctrl.signal
        })()
      })
      const data = await res.json()
      if (data.success) {
        setFinalPackage(data.package)
        setCreditsAfter(data.credits_remaining)
        setCredits(data.credits_remaining)
        localStorage.setItem('morelike_credits', String(data.credits_remaining))
        setFlow('result')
      } else {
        if (res.status === 401 || res.status === 402) {
          setTokenValidated(false)
          setToken('')
          localStorage.removeItem('morelike_token')
          localStorage.removeItem('morelike_credits')
          setFlow('paywall')
          alert(data.error || 'Token expired or no credits.')
        } else {
          alert(data.error || 'Failed to generate package')
          setFlow('pick_title')
        }
      }
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

      const titlesRes = await aiFetch(`${API_URL}/api/generate-titles`, { viral_dna: dnaData.viral_dna })
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

  // ── Paste-subtitles path ────────────────────────────────────
  const handlePasteAndGo = () => {
    if (!pastedSubtitles.trim()) return
    setPipelineError('')
    setFlow('processing')
    setTimeout(() => {
      extractedRef.current = pastedSubtitles
      runPipeline(pastedSubtitles)
    }, 500)
  }

  // ── Start extraction → pipeline ─────────────────────────────
  const handleStart = async () => {
    if (!channelUrl.trim()) return
    setPipelineError('')
    setFlow('processing')

    const sock = io(API_URL)
    socketRef.current = sock

    sock.on('progress', (data) => {
      if (data.status === 'error') {
        setPipelineError(data.message || 'Extraction failed')
        setFlow('input')
        sock.close()
      }
      if (data.status === 'complete') {
        sock.close()
        fetch(`${API_URL}/api/subtitles`, { headers: getApiHeaders(token) })
          .then(r => r.json())
          .then(d => {
            if (d.content) {
              extractedRef.current = d.content
              runPipeline(d.content)
            } else {
              setPipelineError('No transcripts found for this channel.')
              setFlow('input')
            }
          })
          .catch(() => {
            setPipelineError('Failed to retrieve transcripts.')
            setFlow('input')
          })
      }
    })

    try {
      await fetch(`${API_URL}/api/extract`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ channel_url: channelUrl.trim(), limit })
      })
    } catch {
      sock.close()
      setPipelineError('Failed to start extraction.')
      setFlow('input')
    }
  }

  // ── Title chosen ────────────────────────────────────────────
  const handleChooseTitle = (title, customTopic) => {
    setChosenTitle(title)

    if (tokenValidated && credits > 0) {
      // Authenticated — go to visual upload first
      pendingTitle.current = title
      pendingTopic.current = customTopic
      setFlow('visual_upload')
    } else {
      // Hold title and show paywall
      pendingTitle.current = title
      pendingTopic.current = customTopic
      setFlow('paywall')
    }
  }

  // ── Regenerate titles ───────────────────────────────────────
  const handleRegenerateTitles = async () => {
    setFlow('processing')
    try {
      const res = await aiFetch(`${API_URL}/api/generate-titles`, { viral_dna: viralDNA })
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
  const handleDownload = () => {
    const blob = new Blob([finalPackage], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${chosenTitle.slice(0, 40).replace(/[\/:*?"<>|]/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Feedback ────────────────────────────────────────────────
  const handleFeedback = async () => {
    if (!feedbackMsg.trim()) return
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ message: feedbackMsg })
      })
      setFeedbackSent(true)
    } catch {}
  }

  // ── Visual upload handlers ──────────────────────────────────
  const handleVisualUpload = async () => {
    if (visualImages.length < 3) {
      alert('Please upload at least 3 reference images from the channel videos.')
      return
    }
    setFlow('processing')
    try {
      const form = new FormData()
      visualImages.forEach((f) => form.append('images', f))
      const res = await fetch(`${API_URL}/api/analyze-visuals`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form
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
    }
  }

  const handleThumbnailUpload = async () => {
    if (thumbnailImages.length < 2) {
      alert('Please upload at least 2 thumbnail reference images from the channel.')
      return
    }
    setFlow('processing')
    try {
      const form = new FormData()
      thumbnailImages.forEach((f) => form.append('images', f))
      const res = await fetch(`${API_URL}/api/analyze-thumbnails`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form
      })
      const data = await res.json()
      if (data.success) {
        setThumbnailProfile(data.thumbnail_profile)
        thumbnailProfileRef.current = data.thumbnail_profile
        setFlow('generating')
        doGeneratePackage(token, pendingTitle.current, pendingTopic.current, visualProfileRef.current, data.thumbnail_profile)
      } else {
        throw new Error(data.error)
      }
    } catch (e) {
      alert('Thumbnail analysis failed: ' + (e.message || 'Server error'))
      setFlow('thumbnail_upload')
    }
  }

  const handleRemoveVisualImage = (index) => {
    setVisualImages((prev) => prev.filter((_, i) => i !== index))
  }

  const handleRemoveThumbnailImage = (index) => {
    setThumbnailImages((prev) => prev.filter((_, i) => i !== index))
  }

  // ── Reset ───────────────────────────────────────────────────
  const handleReset = () => {
    setFlow('input')
    setChannelUrl('')
    setPastedSubtitles('')
    setViralDNA('')
    setTitles('')
    setParsedTitles([])
    setChosenTitle('')
    setFinalPackage('')
    setPipelineError('')
    setFeedbackMsg('')
    setVisualImages([])
    setThumbnailImages([])
    setVisualProfile(null)
    setThumbnailProfile(null)
    visualProfileRef.current = null
    thumbnailProfileRef.current = null
    setFeedbackSent(false)
    extractedRef.current = ''
    pendingTitle.current = ''
    pendingTopic.current = ''
  }

  // Logout
  const handleLogout = () => {
    setToken('')
    setCredits(0)
    setTokenEmail('')
    setTokenValidated(false)
    localStorage.removeItem('morelike_token')
    localStorage.removeItem('morelike_credits')
  }

  // Cleanup socket on unmount
  useEffect(() => {
    return () => {
      if (socketRef.current) socketRef.current.close()
    }
  }, [])

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
            <span className="text-xs md:text-sm text-gray-400">{tokenEmail && `${tokenEmail} | `}Credits: <strong className="text-white">{credits}</strong></span>
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
              <button onClick={() => setInputMode('paste')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${inputMode === 'paste' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                Paste Subtitles
              </button>
            </div>

            {pipelineError && (
              <div className="mb-4 p-3 bg-red-900/20 border border-red-500/50 rounded-lg text-red-400 text-sm">{pipelineError}</div>
            )}

            {inputMode === 'scrape' ? (
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
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">Videos to analyze (max 3)</label>
                    <input
                      type="number" min="1" max="3"
                      value={limit}
                      onChange={(e) => setLimit(Math.min(3, Math.max(1, parseInt(e.target.value) || 1)))}
                      className="w-24 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">Target video length</label>
                    <select
                      value={videoLength}
                      onChange={(e) => setVideoLength(parseInt(e.target.value))}
                      className="bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      <option value={1}>1 minute</option>
                      <option value={2}>2 minutes</option>
                      <option value={3}>3 minutes</option>
                    </select>
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
            ) : (
              <>
                <textarea
                  placeholder="Paste video subtitles here..."
                  value={pastedSubtitles}
                  onChange={(e) => setPastedSubtitles(e.target.value)}
                  className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-4"
                  rows={8}
                />
                <div className="text-sm text-gray-400 mb-4">{pastedSubtitles.length.toLocaleString()} characters</div>
                <button
                  onClick={handlePasteAndGo}
                  disabled={!pastedSubtitles.trim()}
                  className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
                >
                  Analyze Transcripts (Free)
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
            <div className="relative z-10">
              <h2 className="text-2xl font-bold mb-1 text-white">Analyzing Channel</h2>
              <p className="text-purple-200/50 text-sm mb-2">This may take up to 2 minutes</p>
              <ProgressBar />
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
            <p className="text-gray-500 text-xs mt-4">Selecting a title will prompt you to unlock the full script package — $8 for 3 credits (up to 3 min per video).</p>
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

        {/* ── GENERATING SCREEN ─────────────────────────────── */}
        {flow === 'generating' && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-4 md:p-8 border border-purple-500/30 text-center">
            <h2 className="text-xl font-bold mb-2">Creating Your Package</h2>
            <p className="text-purple-200/50 text-sm mb-8">Synthesizing script, image prompts, and video prompts...</p>
            <ProgressBar />
          </div>
        )}

        {/* ── RESULT SCREEN ─────────────────────────────────── */}
        {flow === 'result' && (
          <>
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
