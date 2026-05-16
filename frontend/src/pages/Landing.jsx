import React from 'react'
import { Link } from 'react-router-dom'

/* ── Step Icon SVG ─────────────────────────────────────────── */

function StepIcon({ icon, color }) {
  return (
    <svg viewBox="0 0 48 48" className="w-14 h-14 mx-auto mb-3" fill="none">
      <circle cx="24" cy="24" r="24" fill={color} opacity="0.15" />
      <circle cx="24" cy="24" r="20" fill={color} opacity="0.3" />
      {icon}
    </svg>
  )
}

/* ── Landing ──────────────────────────────────────────────── */
function Landing() {
  const LEMON_SQUEEZY_URL = import.meta.env.VITE_LEMON_SQUEEZY_URL || 'https://store.lemonsqueezy.com/checkout'

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white relative overflow-hidden">
      {/* Animated background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '2s' }} />
      </div>

      {/* Nav */}
      <nav className="relative z-10 container mx-auto px-4 py-4 md:py-6 flex justify-between items-center max-w-6xl flex-wrap gap-3">
        <div className="flex items-center gap-3 md:gap-5">
          <img
            src="/logo.png"
            alt="Morelike"
            className="w-12 h-12 md:w-20 md:h-20 rounded-2xl object-cover"
            onError={(e) => {
              e.target.style.display = 'none'
              e.target.nextSibling.style.display = 'flex'
            }}
          />
          <div className="w-12 h-12 md:w-20 md:h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center font-extrabold text-white text-lg md:text-3xl shadow-lg shadow-purple-500/30" style={{ display: 'none' }}>M</div>
          <span className="text-2xl md:text-6xl font-extrabold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight">
            Morelike
          </span>
        </div>
        <div className="flex gap-3 md:gap-6 items-center">
          <Link to="/portal" className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">Portal</Link>
          <Link to="/admin" className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">Admin</Link>
          <a
            href={LEMON_SQUEEZY_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 md:px-5 md:py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-lg transition-all transform hover:scale-105 text-xs md:text-sm whitespace-nowrap"
          >
            Get Access — $8
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 container mx-auto px-4 pt-8 md:pt-16 pb-8 md:pb-12 max-w-6xl">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="text-center md:text-left">
            <div className="inline-flex items-center gap-2 bg-purple-900/40 border border-purple-500/30 rounded-full px-3 py-1 md:px-4 md:py-1.5 text-xs md:text-sm text-purple-200 mb-6">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              Free Channel Analysis
            </div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
              Never Run Out of{' '}
              <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Video Ideas</span>
              {' '}Again
            </h1>
            <p className="text-base md:text-lg text-purple-200 mb-8 leading-relaxed max-w-lg">
              Paste any YouTube channel you admire and get fresh title ideas, topic breakdowns, and a deep analysis of what makes their content work — completely free. When you're ready, unlock 3 full script packages for just $8 (up to 3 minutes of video each).
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center md:justify-start">
              <Link
                to="/portal"
                className="px-6 py-3 md:px-8 md:py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold text-base md:text-lg rounded-xl transition-all transform hover:scale-105 shadow-lg text-center"
              >
                Analyze a Channel Free
              </Link>
              <Link
                to="/portal"
                className="px-6 py-3 md:px-8 md:py-4 bg-gray-700 hover:bg-gray-600 text-white font-semibold text-base md:text-lg rounded-xl transition-all text-center"
              >
                Already Have Access
              </Link>
            </div>
            <p className="text-gray-500 text-sm mt-4">
              $8 = 3 credits. Each credit unlocks a full script package (up to 3 min video).
            </p>
          </div>
          <div className="hidden md:block">
            <img
              src="/hero-workspace.png"
              alt="Content creator workspace"
              className="w-full rounded-2xl shadow-2xl border border-purple-500/20"
            />
          </div>
        </div>
      </section>

      {/* Problem / Solution strip */}
      <section className="relative z-10 bg-gray-800/30 border-y border-purple-500/20 py-12">
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="flex items-center gap-8 flex-col md:flex-row">
            <img
              src="/creator-stuck.png"
              alt="Creator stuck at blank screen"
              className="w-32 h-32 md:w-48 md:h-48 rounded-2xl object-cover border border-purple-500/30 shadow-lg flex-shrink-0"
            />
            <p className="text-purple-200 text-base md:text-lg text-center md:text-left">
              <span className="text-gray-400 line-through mr-2">"What should I create today?"</span>
              <span className="text-white font-semibold">"Here are 3 title ideas — pick one and unlock the full package."</span>
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="relative z-10 container mx-auto px-4 py-12 md:py-20 max-w-6xl">
        <h2 className="text-2xl md:text-4xl font-bold text-center mb-4">How It Works</h2>
        <p className="text-purple-200 text-center mb-14 max-w-xl mx-auto">Three simple steps from blank page to production-ready content.</p>
        <div className="grid md:grid-cols-3 gap-8">
          {/* Step 1 */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl p-5 md:p-8 border border-purple-500/20 text-center hover:border-purple-500/40 transition-all">
            <StepIcon
              color="#7c3aed"
              icon={
                <g stroke="white" strokeWidth="1.5" strokeLinecap="round">
                  <rect x="14" y="12" width="20" height="24" rx="3" />
                  <path d="M18 20l4 4 8-8" />
                  <path d="M14 8h20" stroke="#c4b5fd" />
                </g>
              }
            />
            <h3 className="text-lg font-semibold mb-2">1. Paste a Channel</h3>
            <p className="text-gray-400 text-sm leading-relaxed">
              Drop in any YouTube channel you admire. We study what works so you don't have to guess.
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl p-5 md:p-8 border border-purple-500/20 text-center hover:border-purple-500/40 transition-all">
            <StepIcon
              color="#db2777"
              icon={
                <g stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none">
                  <path d="M12 36V12l24-4v28" />
                  <path d="M12 22l24-4" />
                  <path d="M12 30l24-4" />
                  <circle cx="14" cy="12" r="3" fill="white" />
                  <circle cx="14" cy="22" r="3" fill="white" />
                  <circle cx="14" cy="30" r="3" fill="white" />
                </g>
              }
            />
            <h3 className="text-lg font-semibold mb-2">2. Pick a Title</h3>
            <p className="text-gray-400 text-sm leading-relaxed">
              Get 3 fresh title ideas crafted to match your niche. Choose the one that clicks.
            </p>
          </div>

          {/* Step 3 */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl p-5 md:p-8 border border-purple-500/20 text-center hover:border-purple-500/40 transition-all">
            <StepIcon
              color="#f59e0b"
              icon={
                <g stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none">
                  <rect x="8" y="6" width="32" height="36" rx="4" />
                  <path d="M18 20l4 4 8-8" />
                  <path d="M14 30h20" />
                  <path d="M14 34h14" />
                </g>
              }
            />
            <h3 className="text-lg font-semibold mb-2">3. Unlock & Create</h3>
            <p className="text-gray-400 text-sm leading-relaxed">
              Unlock 3 full script packages for $8 — each with a complete script (up to 3 min), image prompts, video prompts, voice direction, and thumbnail design. Ready to download.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="relative z-10 container mx-auto px-4 pb-20 max-w-2xl">
        <div className="bg-gray-800/80 backdrop-blur-lg rounded-3xl border border-purple-500/30 p-6 md:p-10 text-center">
          <div className="inline-block bg-purple-900/40 rounded-full px-4 py-1 text-sm text-purple-300 mb-6">
            How It Works
          </div>
          <div className="flex items-center justify-center gap-4 text-lg mb-8">
            <span className="text-white font-bold">1. Analyze Free</span>
            <span className="text-gray-500">→</span>
            <span className="text-white font-bold">2. Pick a Title</span>
            <span className="text-gray-500">→</span>
            <span className="text-white font-bold">3. Unlock $8</span>
          </div>

          <div className="grid grid-cols-1 gap-3 mb-10 text-left max-w-sm mx-auto">
            {[
              'Analyze any YouTube channel for free',
              'Deep analysis of what makes the channel work',
              '3 SEO-optimized title ideas to choose from',
              'Full script package: dialogue, image & video prompts',
              'Thumbnail A/B test + voiceover direction',
              'Downloadable .txt — ready to create',
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 text-gray-300">
                <svg className="w-5 h-5 mt-0.5 flex-shrink-0" viewBox="0 0 20 20" fill="#22c55e">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>

          <Link
            to="/portal"
            className="block w-full py-3 md:py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold text-base md:text-lg rounded-xl transition-all transform hover:scale-105 shadow-lg"
          >
            Analyze a Channel Free
          </Link>
          <p className="text-gray-500 text-sm mt-4">
            $8 = 3 credits (up to 3 min per video). Pay when you're ready to unlock.{' '}
            <Link to="/success" className="text-purple-400 hover:underline">Already paid? Claim your token</Link>
          </p>
        </div>
      </section>

      {/* Testimonial-style trust strip */}
      <section className="relative z-10 border-t border-gray-800 py-16">
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="flex items-center gap-8 flex-col md:flex-row mb-12">
            <div className="flex-1 text-center md:text-left">
              <h2 className="text-2xl md:text-3xl font-bold mb-4">From Blank Page to <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Published</span></h2>
              <p className="text-gray-400">Your next video idea, script, and production assets — all in one place.</p>
            </div>
            <img
              src="/creator-success.png"
              alt="Happy creator with finished content"
              className="w-40 h-40 md:w-56 md:h-56 rounded-2xl object-cover border border-purple-500/30 shadow-lg flex-shrink-0"
            />
          </div>
          <div className="grid md:grid-cols-3 gap-8 text-center">
            {[
              { stat: 'Fresh Ideas', desc: 'Stop staring at a blank screen. Get titles that are proven to work in your niche.' },
              { stat: 'Save Hours', desc: 'Skip the research phase. Go from idea to finished script in minutes, not days.' },
              { stat: 'Stay Consistent', desc: 'Post more often with less burnout. Your content calendar stays full.' },
            ].map((item) => (
              <div key={item.stat}>
                <div className="text-lg md:text-xl font-bold text-white mb-2">{item.stat}</div>
                <p className="text-gray-400 text-sm">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 text-center py-8 text-gray-500 text-sm border-t border-gray-800">
        &copy; {new Date().getFullYear()} Morelike. Built for creators who want to create more, stress less.
      </footer>
    </div>
  )
}

export default Landing
