import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

function Admin() {
  const [password, setPassword] = useState('')
  const [adminToken, setAdminToken] = useState('')
  const [loginError, setLoginError] = useState('')
  const [tab, setTab] = useState('tokens')

  // Token generator
  const [genEmail, setGenEmail] = useState('')
  const [genPlan, setGenPlan] = useState('basic')
  const [genCredits, setGenCredits] = useState(3)
  const [genResult, setGenResult] = useState(null)
  const [genError, setGenError] = useState('')
  const [genLoading, setGenLoading] = useState(false)
  // Custom plan
  const [customVideos, setCustomVideos] = useState(5)
  const [customMinutes, setCustomMinutes] = useState(15)

  const PLAN_CONFIG = {
    basic:     { max_videos: 3,  max_minutes: 3,  price: '$8',  credits: 3,  label: 'Basic',     color: 'purple', hidden: false },
    pro:       { max_videos: 5,  max_minutes: 5,  price: '$10', credits: 3,  label: 'Pro',       color: 'pink',   hidden: false },
    promax:    { max_videos: 5,  max_minutes: 15, price: '$15', credits: 5,  label: 'Pro Max',   color: 'amber',  hidden: false },
    unlimited: { max_videos: 5,  max_minutes: 60, price: '—',   credits: 9999, label: 'Unlimited', color: 'green', hidden: true },
    custom:    { max_videos: 5,  max_minutes: 15, price: '—',   credits: 1,   label: 'Custom',   color: 'gray',  hidden: true },
  }

  // Feedback
  const [feedback, setFeedback] = useState([])
  const [replies, setReplies] = useState({})
  const [sending, setSending] = useState({})

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginError('')
    try {
      const res = await fetch(`${API_URL}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      })
      const data = await res.json()
      if (data.success) {
        setAdminToken(data.admin_token)
      } else {
        setLoginError('Invalid password')
      }
    } catch {
      setLoginError('Cannot reach server')
    }
  }

  const handleGenerateToken = async (e) => {
    e.preventDefault()
    if (!genEmail.trim()) return
    setGenLoading(true)
    setGenError('')
    setGenResult(null)

    const body = { email: genEmail.trim(), credits: genCredits, plan: genPlan }
    if (genPlan === 'custom') {
      body.custom_limits = { max_videos: customVideos, max_minutes: customMinutes }
    }

    try {
      const res = await fetch(`${API_URL}/api/admin/generate-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Token': adminToken },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (data.success) {
        setGenResult(data)
        setGenEmail('')
      } else {
        setGenError(data.error || 'Failed')
      }
    } catch {
      setGenError('Cannot reach server')
    }
    setGenLoading(false)
  }

  const handlePlanChange = (plan) => {
    setGenPlan(plan)
    const cfg = PLAN_CONFIG[plan]
    if (cfg && cfg.credits) setGenCredits(cfg.credits)
  }

  const loadFeedback = async (token) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/feedback`, {
        headers: { 'X-Admin-Token': token }
      })
      const data = await res.json()
      setFeedback(data.feedback || [])
    } catch {
      // silent
    }
  }

  const handleReply = async (fb) => {
    if (!replies[fb.id]?.trim()) return
    setSending((prev) => ({ ...prev, [fb.id]: true }))
    try {
      await fetch(`${API_URL}/api/admin/reply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify({
          feedback_id: fb.id,
          reply: replies[fb.id],
          email: fb.email
        })
      })
      setReplies((prev) => ({ ...prev, [fb.id]: '' }))
      loadFeedback(adminToken)
    } catch {
      // silent
    }
    setSending((prev) => ({ ...prev, [fb.id]: false }))
  }

  const formatDate = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleString()
  }

  // ── Login screen ──────────────────────────────────────────
  if (!adminToken) {
    return (
      <div className="min-h-screen text-white flex items-center justify-center px-4 relative">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: 'url(/processor.jpg)' }} />
        <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
        <div className="max-w-sm w-full relative z-10">
          <div className="text-center mb-8">
            <div className="text-3xl md:text-4xl mb-4">&#128274;</div>
            <h1 className="text-xl md:text-2xl font-bold">Admin Panel</h1>
          </div>
          <form onSubmit={handleLogin} className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-6 md:p-8">
            <input
              type="password"
              placeholder="Admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-4"
              autoFocus
            />
            {loginError && <p className="text-red-400 text-sm mb-4">{loginError}</p>}
            <button
              type="submit"
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all"
            >
              Login
            </button>
          </form>
          <p className="text-center mt-4 text-gray-500 text-sm">
            <Link to="/" className="text-purple-400 hover:underline">Back to home</Link>
          </p>
        </div>
      </div>
    )
  }

  // ── Dashboard ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <div className="flex gap-3">
            <Link to="/" className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all text-sm">Home</Link>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex flex-col sm:flex-row gap-2 mb-8">
          <button
            onClick={() => setTab('tokens')}
            className={`px-6 py-2 rounded-lg font-semibold transition-all ${tab === 'tokens' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >
            Generate Tokens
          </button>
          <button
            onClick={() => { setTab('feedback'); loadFeedback(adminToken) }}
            className={`px-6 py-2 rounded-lg font-semibold transition-all ${tab === 'feedback' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >
            Feedback
          </button>
        </div>

        {/* Token Generator Tab */}
        {tab === 'tokens' && (
          <div className="space-y-6">
            {/* Plan Reference */}
            <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-6">
              <h2 className="text-xl font-bold mb-4">Plan Reference</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(PLAN_CONFIG).map(([key, cfg]) => (
                  <div key={key} className={`bg-gray-900/50 border rounded-lg p-3 text-center ${
                    key === 'unlimited' ? 'border-green-500/50 bg-green-900/10' :
                    key === 'custom' ? 'border-gray-500/50' :
                    'border-gray-700'
                  }`}>
                    <span className={`text-xs font-bold uppercase ${
                      key === 'unlimited' ? 'text-green-400' :
                      key === 'custom' ? 'text-gray-400' :
                      key === 'promax' ? 'text-amber-400' :
                      key === 'pro' ? 'text-pink-400' : 'text-purple-400'
                    }`}>
                      {cfg.label}
                      {cfg.hidden && <span className="ml-1 text-[10px] opacity-50">(hidden)</span>}
                    </span>
                    <div className="text-white text-sm mt-1 font-mono">{cfg.max_videos}v &middot; {cfg.max_minutes}m</div>
                    <div className="text-gray-400 text-xs">{cfg.credits} credits &middot; {cfg.price}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Generate Token */}
            <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-green-500/30 p-6">
              <h2 className="text-xl font-bold mb-4">Generate Access Token</h2>
              <p className="text-gray-400 text-sm mb-6">Create tokens with any email, plan, and credit count. Hidden plans (Unlimited, Custom) are not visible on the public website.</p>

              {/* Plan Selector */}
              <div className="mb-4">
                <label className="block text-sm text-purple-200 mb-2">Plan</label>
                <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                  {Object.entries(PLAN_CONFIG).map(([key, cfg]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handlePlanChange(key)}
                      className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all border ${
                        genPlan === key
                          ? key === 'unlimited' ? 'bg-green-600 border-green-400 text-white' :
                            key === 'custom' ? 'bg-gray-600 border-gray-400 text-white' :
                            key === 'promax' ? 'bg-amber-600 border-amber-400 text-white' :
                            key === 'pro' ? 'bg-pink-600 border-pink-400 text-white' :
                            'bg-purple-600 border-purple-400 text-white'
                          : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                      }`}
                    >
                      {cfg.label}
                      {cfg.hidden && <div className="text-[10px] opacity-70">hidden</div>}
                      <div className="text-[10px] opacity-70">{cfg.max_videos}v · {cfg.max_minutes}m</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Plan Settings */}
              {genPlan === 'custom' && (
                <div className="bg-gray-900/50 border border-gray-600 rounded-lg p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Max Videos</label>
                    <input type="number" min="1" max="20" value={customVideos}
                      onChange={(e) => setCustomVideos(Math.min(20, Math.max(1, parseInt(e.target.value) || 1)))}
                      className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Max Minutes</label>
                    <input type="number" min="1" max="120" value={customMinutes}
                      onChange={(e) => setCustomMinutes(Math.min(120, Math.max(1, parseInt(e.target.value) || 1)))}
                      className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Credits</label>
                    <input type="number" min="1" max="9999" value={genCredits}
                      onChange={(e) => setGenCredits(Math.min(9999, Math.max(1, parseInt(e.target.value) || 1)))}
                      className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                  </div>
                </div>
              )}

              <form onSubmit={handleGenerateToken} className="flex gap-4 flex-wrap items-end">
                <div className="flex-1 min-w-[200px]">
                  <label className="block text-sm text-purple-200 mb-1">Email</label>
                  <input
                    type="email"
                    placeholder="user@example.com"
                    value={genEmail}
                    onChange={(e) => setGenEmail(e.target.value)}
                    className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    required
                  />
                </div>
                {genPlan !== 'custom' && (
                  <div className="w-32">
                    <label className="block text-sm text-purple-200 mb-1">Credits</label>
                    <input
                      type="number" min="1" max="9999"
                      value={genCredits}
                      onChange={(e) => setGenCredits(Math.min(9999, Math.max(1, parseInt(e.target.value) || 1)))}
                      className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                )}
                <button
                  type="submit"
                  disabled={genLoading || !genEmail.trim()}
                  className={`px-6 py-2 text-white font-bold rounded-lg transition-all disabled:opacity-50 ${
                    genPlan === 'unlimited' ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700' :
                    genPlan === 'custom' ? 'bg-gradient-to-r from-gray-500 to-gray-600 hover:from-gray-600 hover:to-gray-700' :
                    'bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700'
                  }`}
                >
                  {genLoading ? 'Generating...' : 'Generate'}
                </button>
              </form>
              {genError && <p className="mt-3 text-red-400 text-sm">{genError}</p>}
              {genResult && (
                <div className="mt-4 p-4 bg-green-900/20 border border-green-500/30 rounded-lg">
                  <p className="text-green-400 text-sm">Token created!</p>
                  <p className="text-white font-mono text-lg mt-1">{genResult.token}</p>
                  <p className="text-gray-400 text-sm mt-1">
                    {genResult.email} &middot; {genResult.plan}{genResult.custom_limits ? ` (${genResult.custom_limits.max_videos}v · ${genResult.custom_limits.max_minutes}m)` : ''} &middot; {genResult.credits} credits
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Feedback Tab */}
        {tab === 'feedback' && (
          <>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">User Feedback</h2>
              <button
                onClick={() => loadFeedback(adminToken)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all text-sm"
              >
                Refresh
              </button>
            </div>

            {feedback.length === 0 ? (
              <div className="text-center py-20 text-gray-400">
                <div className="text-5xl mb-4">&#128221;</div>
                <p>No feedback yet.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {feedback.map((fb) => (
                  <div key={fb.id} className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-6">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <span className="text-purple-300 font-mono text-sm">{fb.email || 'No email'}</span>
                        <span className="text-gray-500 mx-2">|</span>
                        <span className="text-gray-500 text-sm">{formatDate(fb.created_at)}</span>
                      </div>
                      {fb.replied_at ? (
                        <span className="text-xs bg-green-900/50 text-green-400 px-3 py-1 rounded-full">Replied</span>
                      ) : (
                        <span className="text-xs bg-yellow-900/50 text-yellow-400 px-3 py-1 rounded-full">Pending</span>
                      )}
                    </div>

                    <div className="bg-gray-900/50 rounded-lg p-4 mb-4">
                      <p className="text-gray-300 whitespace-pre-wrap">{fb.message}</p>
                    </div>

                    {fb.reply && (
                      <div className="bg-purple-900/30 border border-purple-500/30 rounded-lg p-4 mb-4">
                        <p className="text-xs text-purple-300 mb-1">Your reply ({formatDate(fb.replied_at)}):</p>
                        <p className="text-gray-300">{fb.reply}</p>
                      </div>
                    )}

                    <div className="flex flex-col gap-2">
                      <textarea
                        placeholder="Write a reply..."
                        value={replies[fb.id] || ''}
                        onChange={(e) => setReplies((prev) => ({ ...prev, [fb.id]: e.target.value }))}
                        className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm resize-none"
                        rows={2}
                      />
                      <button
                        onClick={() => handleReply(fb)}
                        disabled={sending[fb.id] || !replies[fb.id]?.trim()}
                        className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed text-sm self-stretch sm:self-end"
                      >
                        {sending[fb.id] ? 'Sending...' : 'Reply'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <p className="text-center mt-8 text-gray-500 text-sm">
          <Link to="/" className="text-purple-400 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  )
}

export default Admin
