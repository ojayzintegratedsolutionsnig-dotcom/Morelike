import React from 'react'
import { Link } from 'react-router-dom'

function CheckIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 20 20" fill="#22c55e">
      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
    </svg>
  )
}

function Plans() {
  const LEMON_SQUEEZY_URL = import.meta.env.VITE_LEMON_SQUEEZY_URL || 'https://morelike.lemonsqueezy.com/checkout/buy/0772c25a-3fa9-4ca4-b229-7c7fbdd04127'
  const LEMON_SQUEEZY_URL_PRO = import.meta.env.VITE_LEMON_SQUEEZY_URL_PRO || 'https://morelike.lemonsqueezy.com/checkout/buy/pro-product-id'
  const LEMON_SQUEEZY_URL_PROMAX = import.meta.env.VITE_LEMON_SQUEEZY_URL_PROMAX || 'https://morelike.lemonsqueezy.com/checkout/buy/promax-product-id'

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#111111] via-[#1a1510] to-[#151018] text-white relative overflow-hidden">
      {/* Animated background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply blur-xl opacity-20 animate-pulse-slow" style={{ animationDelay: '2s' }} />
      </div>

      {/* Nav */}
      <nav className="relative z-10 container mx-auto px-4 py-4 md:py-6 flex justify-between items-center max-w-6xl">
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
          <Link to="/" className="text-2xl md:text-6xl font-extrabold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight">
            Morelike
          </Link>
        </div>
        <div className="flex gap-3 md:gap-6 items-center">
          <Link to="/portal" className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">Portal</Link>
          <Link to="/" className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">Home</Link>
        </div>
      </nav>

      {/* Header */}
      <section className="relative z-10 container mx-auto px-4 pt-4 md:pt-8 pb-8 max-w-6xl text-center">
        <h1 className="text-3xl md:text-5xl font-bold mb-4">
          Choose Your <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Plan</span>
        </h1>
        <p className="text-purple-200 text-sm md:text-base max-w-md mx-auto">
          One-time purchase. Credits vary by plan. Pay when you're ready to unlock.
        </p>
      </section>

      {/* Plan Cards */}
      <section className="relative z-10 container mx-auto px-4 pb-8 max-w-4xl">
        <div className="grid md:grid-cols-3 gap-6">
          {/* Basic */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl border border-purple-500/20 p-6 md:p-8 flex flex-col">
            <h2 className="text-xl md:text-2xl font-bold mb-1">Basic</h2>
            <p className="text-3xl md:text-4xl font-extrabold mb-6">
              $8<span className="text-base font-normal text-gray-400">/one-time</span>
            </p>
            <ul className="space-y-3 mb-8 flex-1">
              {[
                '3 credits (3 script packages)',
                'Up to 3 minutes per video',
                'Up to 3 videos',
                'Full script with dialogue',
                'Image prompts',
                'Voiceover direction',
                'Thumbnail A/B test',
                'SEO title & description',
                'Downloadable .txt',
              ].map((feature) => (
                <li key={feature} className="flex items-start gap-3 text-gray-300 text-sm">
                  <CheckIcon />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <a
              href={LEMON_SQUEEZY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-3 text-center bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold rounded-xl transition-all transform hover:scale-105 shadow-lg"
            >
              Select Basic
            </a>
          </div>

          {/* Pro */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl border border-pink-500/30 p-6 md:p-8 flex flex-col relative">
            <div className="absolute -top-3 right-4 bg-gradient-to-r from-pink-500 to-rose-500 text-white text-xs font-bold px-3 py-1 rounded-full">
              Popular
            </div>
            <h2 className="text-xl md:text-2xl font-bold mb-1">Pro</h2>
            <p className="text-3xl md:text-4xl font-extrabold mb-6">
              $10<span className="text-base font-normal text-gray-400">/one-time</span>
            </p>
            <ul className="space-y-3 mb-8 flex-1">
              {[
                '3 credits (3 script packages)',
                'Up to 5 minutes per video',
                'Up to 5 videos',
                'Full script with dialogue',
                'Detailed image prompts',
                'Full video prompts (camera angles, multi-shot, scene direction)',
                'Voiceover direction',
                'Thumbnail A/B test',
                'SEO title & description',
                'Downloadable .txt',
              ].map((feature) => (
                <li key={feature} className="flex items-start gap-3 text-gray-300 text-sm">
                  <CheckIcon />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <a
              href={LEMON_SQUEEZY_URL_PRO}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-3 text-center bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white font-bold rounded-xl transition-all transform hover:scale-105 shadow-lg"
            >
              Select Pro
            </a>
          </div>

          {/* Pro Max */}
          <div className="bg-gray-800/60 backdrop-blur rounded-2xl border border-amber-500/30 p-6 md:p-8 flex flex-col relative">
            <div className="absolute -top-3 right-4 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold px-3 py-1 rounded-full">
              Best Value
            </div>
            <h2 className="text-xl md:text-2xl font-bold mb-1">Pro Max</h2>
            <p className="text-3xl md:text-4xl font-extrabold mb-6">
              $15<span className="text-base font-normal text-gray-400">/one-time</span>
            </p>
            <ul className="space-y-3 mb-8 flex-1">
              {[
                '5 credits (5 script packages)',
                'Up to 15 minutes per video',
                'Up to 5 videos',
                'Full script with dialogue',
                'Detailed image prompts',
                'Full video prompts (camera angles, multi-shot, scene direction)',
                'Voiceover direction',
                'Thumbnail A/B test',
                '5 title ideas per generation',
                'SEO title & description',
                'Downloadable .txt',
              ].map((feature) => (
                <li key={feature} className="flex items-start gap-3 text-gray-300 text-sm">
                  <CheckIcon />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <a
              href={LEMON_SQUEEZY_URL_PROMAX}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full py-3 text-center bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white font-bold rounded-xl transition-all transform hover:scale-105 shadow-lg"
            >
              Select Pro Max
            </a>
          </div>
        </div>

        <div className="text-center mt-8">
          <Link
            to="/portal"
            className="inline-block px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-all text-sm"
          >
            Or Analyze a Channel Free First
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 text-center py-8 text-gray-500 text-sm border-t border-gray-800">
        &copy; {new Date().getFullYear()} Morelike. Built for creators who want to create more, stress less.
      </footer>
    </div>
  )
}

export default Plans
