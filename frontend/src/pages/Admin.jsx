import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

function Admin() {
  const [password, setPassword] = useState('')
  const [adminToken, setAdminToken] = useState('')
  const [feedback, setFeedback] = useState([])
  const [replies, setReplies] = useState({})
  const [sending, setSending] = useState({})
  const [loginError, setLoginError] = useState('')

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
        loadFeedback(data.admin_token)
      } else {
        setLoginError('Invalid password')
      }
    } catch {
      setLoginError('Cannot reach server')
    }
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

  // Login screen
  if (!adminToken) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white flex items-center justify-center px-4">
        <div className="max-w-sm w-full">
          <div className="text-center mb-8">
            <div className="text-4xl mb-4">&#128274;</div>
            <h1 className="text-2xl font-bold">Admin Panel</h1>
          </div>
          <form onSubmit={handleLogin} className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-8">
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

  // Feedback dashboard
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">Feedback Dashboard</h1>
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

                <div className="flex gap-3">
                  <textarea
                    placeholder="Write a reply..."
                    value={replies[fb.id] || ''}
                    onChange={(e) => setReplies((prev) => ({ ...prev, [fb.id]: e.target.value }))}
                    className="flex-1 bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm resize-none"
                    rows={2}
                  />
                  <button
                    onClick={() => handleReply(fb)}
                    disabled={sending[fb.id] || !replies[fb.id]?.trim()}
                    className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed text-sm self-end"
                  >
                    {sending[fb.id] ? 'Sending...' : 'Reply'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="text-center mt-8 text-gray-500 text-sm">
          <Link to="/" className="text-purple-400 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  )
}

export default Admin
