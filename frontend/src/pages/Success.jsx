import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

function Success() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [token, setToken] = useState('')
  const [credits, setCredits] = useState(0)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const handleClaim = async (e) => {
    e.preventDefault()
    setError('')

    if (!email.endsWith('@gmail.com')) {
      setError('Only @gmail.com emails are accepted.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/claim-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() })
      })
      const data = await res.json()
      if (data.success) {
        setToken(data.token)
        setCredits(data.credits)
      } else {
        setError(data.error || 'Something went wrong.')
      }
    } catch {
      setError('Cannot reach server. Please try again later.')
    }
    setLoading(false)
  }

  const copyToken = () => {
    navigator.clipboard.writeText(token)
    setCopied(true)
    setTimeout(() => setCopied(false), 3000)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="text-5xl md:text-6xl mb-4">&#127881;</div>
          <h1 className="text-2xl md:text-3xl font-bold mb-2">Payment Successful!</h1>
          <p className="text-purple-200">Enter your Gmail to get your access token.</p>
        </div>

        <div className="bg-gray-800/80 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-6 md:p-8">
          {!token ? (
            <form onSubmit={handleClaim}>
              <label className="block text-sm text-purple-200 mb-2">Your Gmail address</label>
              <input
                type="email"
                placeholder="you@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-gray-900/50 border border-purple-500/50 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 mb-4"
                required
              />
              {error && (
                <div className="mb-4 p-3 bg-red-900/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
                  <p>{error}</p>
                  {error.includes('No completed purchase') && (
                    <p className="mt-2 text-gray-400 text-xs">
                      Make sure you completed payment on Lemon Squeezy with this Gmail address.
                      The token is sent to your email automatically after purchase — check your inbox and spam folder.
                    </p>
                  )}
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105 disabled:from-gray-600 disabled:to-gray-700 disabled:scale-100 disabled:cursor-not-allowed"
              >
                {loading ? 'Verifying...' : 'Get My Token'}
              </button>
            </form>
          ) : (
            <div className="text-center">
              <div className="text-green-400 text-lg font-semibold mb-2">Token generated!</div>
              <p className="text-sm text-gray-400 mb-4">Also emailed to {email}</p>
              <div className="bg-gray-900/70 rounded-lg p-4 mb-4">
                <code className="text-2xl font-mono text-purple-300 tracking-wider select-all">{token}</code>
              </div>
              <div className="text-sm text-gray-400 mb-6">Credits: <span className="text-white font-bold">{credits}</span></div>
              <button
                onClick={copyToken}
                className="w-full py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all mb-3 text-sm"
              >
                {copied ? 'Copied!' : 'Copy Token'}
              </button>
              <Link
                to="/portal"
                className="block w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-lg transition-all transform hover:scale-105"
              >
                Go to Portal
              </Link>
            </div>
          )}
        </div>

        <p className="text-center mt-6 text-gray-500 text-sm">
          <Link to="/" className="text-purple-400 hover:underline">Back to home</Link>
        </p>
      </div>
    </div>
  )
}

export default Success
