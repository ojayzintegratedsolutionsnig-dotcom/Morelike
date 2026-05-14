import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import io from 'socket.io-client'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

/* ── Helpers ───────────────────────────────────────────────── */
const getStatusColor = (status) => {
  if (status === 'complete') return 'text-green-400'
  if (status === 'error') return 'text-red-400'
  if (status === 'warning') return 'text-yellow-400'
  if (status === 'extracting' || status === 'scanning') return 'text-blue-400'
  return 'text-gray-400'
}

const getApiHeaders = (token) => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token}`
})

/* ── Step Indicator ────────────────────────────────────────── */
function StepIndicator({ currentStep, totalSteps = 4 }) {
  const labels = ['Extract', 'Analyze', 'Pick Title', 'Script']
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {labels.map((label, i) => {
        const step = i + 1
        const active = step <= currentStep
        return (
          <React.Fragment key={label}>
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${active ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white' : 'bg-gray-700 text-gray-400'}`}>
                {active ? '✓' : step}
              </div>
              <span className={`text-sm hidden sm:inline ${active ? 'text-white' : 'text-gray-500'}`}>{label}</span>
            </div>
            {step < totalSteps && (
              <div className={`w-8 h-0.5 ${step < currentStep ? 'bg-purple-500' : 'bg-gray-700'}`} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

/* ── Main Portal ───────────────────────────────────────────── */
function Portal() {
  // Token
  const [token, setToken] = useState('')
  const [credits, setCredits] = useState(0)
  const [tokenEmail, setTokenEmail] = useState('')
  const [tokenValidated, setTokenValidated] = useState(false)

  // Steps
  const [currentStep, setCurrentStep] = useState(1)
  const [inputMode, setInputMode] = useState('scrape')

  // Extraction state
  const [channelUrl, setChannelUrl] = useState('')
  const [limit, setLimit] = useState(10)
  const [isExtracting, setIsExtracting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [logs, setLogs] = useState([])
  const [socket, setSocket] = useState(null)
  const [extractedSubtitles, setExtractedSubtitles] = useState('')
  const [videosProcessed, setVideosProcessed] = useState(0)
  const [pastedSubtitles, setPastedSubtitles] = useState('')

  // AI state
  const [isGeneratingDNA, setIsGeneratingDNA] = useState(false)
  const [viralDNA, setViralDNA] = useState('')
  const [isGeneratingTitles, setIsGeneratingTitles] = useState(false)
  const [titles, setTitles] = useState('')
  const [parsedTitles, setParsedTitles] = useState([])
  const [chosenTitle, setChosenTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [isGeneratingPackage, setIsGeneratingPackage] = useState(false)
  const [finalPackage, setFinalPackage] = useState('')
  const [creditsAfter, setCreditsAfter] = useState(0)

  // Feedback
  const [feedbackMsg, setFeedbackMsg] = useState('')
  const [feedbackSent, setFeedbackSent] = useState(false)

  // ── Token validation ──────────────────────────────
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
      } else {
        alert('Invalid or expired token.')
      }
    } catch {
      alert('Cannot reach server.')
    }
  }

  // ── Socket.IO ─────────────────────────────────────
  const addLog = useCallback((message, status) => {
    setLogs((prev) => [...prev, { message, status, time: new Date().toLocaleTimeString() }])
  }, [])

  useEffect(() => {
    if (!tokenValidated) return
    const newSocket = io(API_URL)
    setSocket(newSocket)
    newSocket.on('connect', () => addLog('Connected to server', 'success'))
    newSocket.on('progress', (data) => {
      setProgress(data.progress || 0)
      setStatusMessage(data.message || '')
      addLog(data.message, data.status)
      if (data.status === 'complete') {
        setIsExtracting(false)
        if (data.videos_processed !== undefined) setVideosProcessed(data.videos_processed)
        fetchSubtitles()
      }
      if (data.status === 'error') setIsExtracting(false)
    })
    newSocket.on('disconnect', () => addLog('Disconnected', 'warning'))
    return () => { newSocket.close() }
  }, [tokenValidated])

  // ── Data fetching ─────────────────────────────────
  const fetchSubtitles = async () => {
    try {
      const res = await fetch(`${API_URL}/api/subtitles`, { headers: getApiHeaders(token) })
      const data = await res.json()
      if (data.content) {
        setExtractedSubtitles(data.content)
        setVideosProcessed(data.videos_processed || 0)
      }
    } catch {}
  }

  // ── Step 1: Extract ──────────────────────────────
  const handleExtract = async () => {
    if (!channelUrl.trim()) return
    setIsExtracting(true)
    setLogs([])
    setExtractedSubtitles('')
    try {
      await fetch(`${API_URL}/api/extract`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ channel_url: channelUrl.trim(), limit })
      })
    } catch {
      setIsExtracting(false)
      addLog('Failed to start extraction', 'error')
    }
  }

  const handleSkipToStep2 = () => {
    if (!pastedSubtitles.trim()) return
    setExtractedSubtitles(pastedSubtitles)
    setCurrentStep(2)
  }

  // ── Step 2: Generate Viral DNA ────────────────────
  const handleGenerateDNA = async () => {
    setIsGeneratingDNA(true)
    try {
      const res = await fetch(`${API_URL}/api/generate-viral-dna`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ subtitles: extractedSubtitles })
      })
      const data = await res.json()
      if (data.success) {
        setViralDNA(data.viral_dna)
        setCurrentStep(3)
      } else {
        alert(data.error || 'Failed to generate analysis')
      }
    } catch {
      alert('Failed to reach server')
    }
    setIsGeneratingDNA(false)
  }

  // ── Step 3: Generate Titles ───────────────────────
  const handleGenerateTitles = async () => {
    setIsGeneratingTitles(true)
    try {
      const res = await fetch(`${API_URL}/api/generate-titles`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ viral_dna: viralDNA })
      })
      const data = await res.json()
      if (data.success) {
        setTitles(data.titles)
        // Parse numbered titles from response
        const lines = data.titles.split('\n').filter((l) => /^\d+[\.\)]/.test(l.trim()))
        setParsedTitles(lines.map((l) => l.replace(/^\d+[\.\)]\s*/, '').trim()))
      } else {
        alert(data.error || 'Failed to generate titles')
      }
    } catch {
      alert('Failed to reach server')
    }
    setIsGeneratingTitles(false)
  }

  const handleChooseTitle = (title) => {
    setChosenTitle(title)
    setCurrentStep(4)
  }

  // ── Step 4: Generate Package ──────────────────────
  const handleGeneratePackage = async () => {
    if (!chosenTitle) return
    setIsGeneratingPackage(true)
    try {
      const res = await fetch(`${API_URL}/api/generate-package`, {
        method: 'POST',
        headers: getApiHeaders(token),
        body: JSON.stringify({ viral_dna: viralDNA, title: chosenTitle, topic })
      })
      const data = await res.json()
      if (data.success) {
        setFinalPackage(data.package)
        setCreditsAfter(data.credits_remaining)
        setCredits(data.credits_remaining)
      } else {
        alert(data.error || 'Failed to generate package')
      }
    } catch {
      alert('Failed to reach server')
    }
    setIsGeneratingPackage(false)
  }

  const handleDownload = () => {
    const blob = new Blob([finalPackage], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${chosenTitle.slice(0, 40).replace(/[\/:*?"<>|]/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Feedback ──────────────────────────────────────
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

  const handleReset = () => {
    setCurrentStep(1)
    setExtractedSubtitles('')
    setPastedSubtitles('')
    setViralDNA('')
    setTitles('')
    setParsedTitles([])
    setChosenTitle('')
    setTopic('')
    setFinalPackage('')
    setLogs([])
    setFeedbackMsg('')
    setFeedbackSent(false)
  }

  // ── TOKEN GATE ──────────────────────────────────────────
  if (!tokenValidated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white flex items-center justify-center px-4">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">&#128273;</div>
            <h1 className="text-3xl font-bold mb-2">Access Portal</h1>
            <p className="text-purple-200">Enter your token to get started.</p>
          </div>
          <form onSubmit={handleValidateToken} className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-8">
            <input
              type="text"
              placeholder="Paste your access token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-4 font-mono"
              autoFocus
              required
            />
            <button
              type="submit"
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105"
            >
              Access Tool
            </button>
          </form>
          <p className="text-center mt-4 text-gray-500 text-sm">
            <Link to="/" className="text-purple-400 hover:underline">Don't have a token? Get one</Link>
          </p>
        </div>
      </div>
    )
  }

  // ── PORTAL ───────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white relative overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow"></div>
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '1s' }}></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '2s' }}></div>
      </div>

      <div className="relative z-10 container mx-auto px-4 py-8 max-w-5xl">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
          <img
            src="/logo.png"
            alt="Morelike"
            className="w-12 h-12 rounded-xl object-cover"
            onError={(e) => {
              e.target.style.display = 'none'
              e.target.nextSibling.style.display = 'flex'
            }}
          />
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center font-extrabold text-white text-xl shadow-lg shadow-purple-500/30" style={{ display: 'none' }}>
            M
          </div>
          <span className="text-3xl font-extrabold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight">Morelike</span>
        </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{tokenEmail && `${tokenEmail} | `}Credits: <strong className="text-white">{credits}</strong></span>
            <Link to="/" className="text-sm text-gray-400 hover:text-white transition-colors">Home</Link>
          </div>
        </div>

        <StepIndicator currentStep={currentStep} />

        {/* ── STEP 1: Extract ───────────────────────────── */}
        {currentStep === 1 && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-purple-500/30">
            <h2 className="text-2xl font-bold mb-2">Step 1: Get Video Subtitles</h2>
            <p className="text-purple-200 mb-6">Extract transcripts from a YouTube channel's most popular videos.</p>

            {/* Mode toggle */}
            <div className="flex gap-2 mb-6">
              <button onClick={() => setInputMode('scrape')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${inputMode === 'scrape' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                Scrape from YouTube
              </button>
              <button onClick={() => setInputMode('paste')} className={`px-4 py-2 rounded-lg font-semibold transition-all ${inputMode === 'paste' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                Paste Subtitles
              </button>
            </div>

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
                      disabled={isExtracting}
                      className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-purple-200 mb-1">Videos to extract (1-20)</label>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      value={limit}
                      onChange={(e) => setLimit(Math.min(20, Math.max(1, parseInt(e.target.value) || 1)))}
                      disabled={isExtracting}
                      className="w-24 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50"
                    />
                  </div>
                </div>

                <button
                  onClick={handleExtract}
                  disabled={isExtracting || !channelUrl.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
                >
                  {isExtracting ? 'Extracting...' : 'Start Extraction'}
                </button>
              </>
            ) : (
              <>
                <textarea
                  placeholder="Paste video subtitles here..."
                  value={pastedSubtitles}
                  onChange={(e) => setPastedSubtitles(e.target.value)}
                  className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-4"
                  rows={12}
                />
                <div className="text-sm text-gray-400 mb-4">{pastedSubtitles.length.toLocaleString()} characters</div>
                <button
                  onClick={handleSkipToStep2}
                  disabled={!pastedSubtitles.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
                >
                  Continue to Step 2
                </button>
              </>
            )}

            {/* Progress bar */}
            {isExtracting && (
              <div className="mt-6">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-purple-200">{statusMessage}</span>
                  <span className="text-purple-300">{progress}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                  <div className="bg-gradient-to-r from-purple-500 to-pink-500 h-full transition-all duration-500 ease-out rounded-full" style={{ width: `${progress}%` }}>
                    <div className="w-full h-full animate-pulse bg-white/20" />
                  </div>
                </div>
              </div>
            )}

            {/* Activity log */}
            {logs.length > 0 && (
              <div className="mt-6 bg-gray-900/50 rounded-lg p-4 max-h-48 overflow-y-auto">
                <div className="text-xs text-gray-500 mb-2">Activity Log</div>
                {logs.map((log, i) => (
                  <div key={i} className={`text-xs ${getStatusColor(log.status)} mb-1`}>
                    <span className="text-gray-600 mr-2">{log.time}</span>
                    {log.message}
                  </div>
                ))}
              </div>
            )}

            {/* Success banner */}
            {!isExtracting && extractedSubtitles && (
              <div className="mt-6 bg-green-900/20 border border-green-500/50 rounded-lg p-4">
                <p className="text-green-400 font-semibold">Extraction Complete!</p>
                <p className="text-green-300 text-sm">Successfully extracted {videosProcessed} video transcripts</p>
                <button onClick={() => setCurrentStep(2)} className="mt-3 px-6 py-2 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white font-semibold rounded-lg transition-all">
                  Continue to Step 2
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 2: Analyze ────────────────────────────── */}
        {currentStep === 2 && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-purple-500/30">
            <h2 className="text-2xl font-bold mb-2">Step 2: Review & Analyze</h2>
            <p className="text-purple-200 mb-6">AI will reverse-engineer the viral formula from these transcripts.</p>

            {/* Subtitles preview */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-purple-200">Extracted Subtitles</span>
                <div className="flex gap-2">
                  <button onClick={() => navigator.clipboard.writeText(extractedSubtitles)} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all text-sm">
                    Copy
                  </button>
                </div>
              </div>
              <pre className="bg-gray-900/50 rounded-lg p-4 text-gray-300 text-sm whitespace-pre-wrap font-mono max-h-64 overflow-y-auto">
                {extractedSubtitles.slice(0, 3000)}{extractedSubtitles.length > 3000 && '\n\n... (truncated)'}
              </pre>
              <div className="text-sm text-gray-500 mt-1">{extractedSubtitles.length.toLocaleString()} characters | {videosProcessed} videos</div>
            </div>

            {!viralDNA ? (
              <button
                onClick={handleGenerateDNA}
                disabled={isGeneratingDNA}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
              >
                {isGeneratingDNA ? 'Analyzing with AI...' : 'Generate Viral DNA Analysis'}
              </button>
            ) : (
              <div className="bg-purple-900/20 border border-purple-500/30 rounded-lg p-6">
                <div className="text-green-400 font-semibold mb-2">Viral DNA Generated!</div>
                <div className="text-sm text-gray-400 mb-4">Analysis complete. Click below to get title ideas.</div>
                <button onClick={() => setCurrentStep(3)} className="px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white font-bold rounded-lg transition-all">
                  Continue to Step 3
                </button>
              </div>
            )}

            {isGeneratingDNA && (
              <div className="mt-4 flex items-center gap-3 text-purple-300">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400" />
                <span>AI is reverse-engineering the viral algorithm...</span>
              </div>
            )}

            <button onClick={() => setCurrentStep(1)} className="mt-6 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
              Back to Step 1
            </button>
          </div>
        )}

        {/* ── STEP 3: Pick Title ─────────────────────────── */}
        {currentStep === 3 && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-purple-500/30">
            <h2 className="text-2xl font-bold mb-2">Step 3: Choose a Title</h2>
            <p className="text-purple-200 mb-6">AI generates 3 title ideas based on the Viral DNA. Pick one to build your script around.</p>

            {!titles ? (
              <button
                onClick={handleGenerateTitles}
                disabled={isGeneratingTitles}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
              >
                {isGeneratingTitles ? 'Generating Ideas...' : 'Generate 5 Title Ideas'}
              </button>
            ) : (
              <>
                <div className="space-y-3 mb-6">
                  {parsedTitles.map((title, i) => (
                    <button
                      key={i}
                      onClick={() => handleChooseTitle(title)}
                      className={`w-full text-left p-4 rounded-lg border transition-all ${chosenTitle === title ? 'border-purple-400 bg-purple-900/30' : 'border-gray-700 bg-gray-900/50 hover:border-purple-500/50'}`}
                    >
                      <span className="text-purple-300 font-bold mr-2">#{i + 1}</span>
                      <span className="text-white">{title}</span>
                    </button>
                  ))}
                </div>

                {/* Or type custom topic */}
                <div className="border-t border-gray-700 pt-4 mb-6">
                  <label className="block text-sm text-purple-200 mb-2">Or type your own topic/angle (optional):</label>
                  <input
                    type="text"
                    placeholder="e.g., The hidden psychology behind..."
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                  />
                </div>
              </>
            )}

            {isGeneratingTitles && (
              <div className="mt-4 flex items-center gap-3 text-purple-300">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400" />
                <span>AI is brainstorming title ideas...</span>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setCurrentStep(2)} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
                Back to Step 2
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 4: Script Package ─────────────────────── */}
        {currentStep === 4 && (
          <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-purple-500/30">
            <h2 className="text-2xl font-bold mb-2">Step 4: Your Viral Script Package</h2>
            <p className="text-purple-200 mb-6">Chosen: <strong className="text-white">{chosenTitle}</strong></p>

            {!finalPackage ? (
              <button
                onClick={handleGeneratePackage}
                disabled={isGeneratingPackage || credits <= 0}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
              >
                {isGeneratingPackage ? 'Generating Package...' : credits <= 0 ? 'No Credits Remaining' : 'Generate Full Package (uses 1 credit)'}
              </button>
            ) : (
              <>
                {/* Package output */}
                <div className="bg-gray-900/70 border border-green-500/50 rounded-lg p-6 mb-4">
                  <div className="text-green-400 font-semibold mb-2">Package Generated!</div>
                  {creditsAfter !== undefined && (
                    <div className="text-sm text-gray-400 mb-4">Credits remaining: <strong className="text-white">{creditsAfter}</strong></div>
                  )}
                  <pre className="text-gray-300 text-sm whitespace-pre-wrap font-mono max-h-96 overflow-y-auto">
                    {finalPackage}
                  </pre>
                </div>

                <div className="flex gap-3 mb-6">
                  <button onClick={handleDownload} className="px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700 text-white font-bold rounded-lg transition-all">
                    Download .txt
                  </button>
                  <button onClick={() => navigator.clipboard.writeText(finalPackage)} className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
                    Copy All
                  </button>
                </div>

                {/* Feedback */}
                <div className="border-t border-gray-700 pt-6">
                  <h3 className="text-lg font-semibold mb-2">How was your experience?</h3>
                  {feedbackSent ? (
                    <p className="text-green-400">Thank you! Your feedback has been submitted.</p>
                  ) : (
                    <div className="flex gap-3">
                      <input
                        type="text"
                        placeholder="Share your thoughts..."
                        value={feedbackMsg}
                        onChange={(e) => setFeedbackMsg(e.target.value)}
                        className="flex-1 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                      />
                      <button onClick={handleFeedback} disabled={!feedbackMsg.trim()} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-all disabled:bg-gray-600 disabled:cursor-not-allowed">
                        Send
                      </button>
                    </div>
                  )}
                </div>

                {/* Reset */}
                <button onClick={handleReset} className="mt-6 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
                  Start Over
                </button>
              </>
            )}

            {isGeneratingPackage && (
              <div className="mt-4 flex items-center gap-3 text-purple-300">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400" />
                <span>AI is engineering your viral script...</span>
              </div>
            )}

            {!finalPackage && (
              <button onClick={() => setCurrentStep(3)} className="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all">
                Back to Step 3
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default Portal
