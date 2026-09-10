import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'

/* Team power ratings (approximate current-form power ratings; edit as needed) */
const DEFAULT_TEAMS = [
  { name: 'Kansas City Chiefs',   rating: 6.5,  pace: 63, offEPA: 0.14, defEPA: -0.05, passRate: 0.62 },
  { name: 'Buffalo Bills',        rating: 5.8,  pace: 65, offEPA: 0.12, defEPA: -0.03, passRate: 0.60 },
  { name: 'San Francisco 49ers',  rating: 5.5,  pace: 62, offEPA: 0.11, defEPA: -0.08, passRate: 0.55 },
  { name: 'Philadelphia Eagles',  rating: 5.0,  pace: 64, offEPA: 0.10, defEPA: -0.04, passRate: 0.58 },
  { name: 'Baltimore Ravens',     rating: 5.2,  pace: 63, offEPA: 0.09, defEPA: -0.06, passRate: 0.52 },
  { name: 'Detroit Lions',        rating: 4.8,  pace: 66, offEPA: 0.11, defEPA:  0.01, passRate: 0.59 },
  { name: 'Dallas Cowboys',       rating: 3.5,  pace: 64, offEPA: 0.05, defEPA: -0.02, passRate: 0.61 },
  { name: 'Miami Dolphins',       rating: 3.2,  pace: 68, offEPA: 0.06, defEPA:  0.02, passRate: 0.60 },
  { name: 'Cincinnati Bengals',   rating: 3.0,  pace: 63, offEPA: 0.07, defEPA:  0.03, passRate: 0.62 },
  { name: 'Green Bay Packers',    rating: 3.8,  pace: 64, offEPA: 0.06, defEPA: -0.01, passRate: 0.58 },
  { name: 'Houston Texans',       rating: 3.5,  pace: 62, offEPA: 0.04, defEPA: -0.02, passRate: 0.59 },
  { name: 'Los Angeles Rams',     rating: 3.0,  pace: 63, offEPA: 0.05, defEPA:  0.01, passRate: 0.60 },
  { name: 'Los Angeles Chargers', rating: 2.8,  pace: 61, offEPA: 0.03, defEPA: -0.03, passRate: 0.57 },
  { name: 'Minnesota Vikings',    rating: 2.5,  pace: 65, offEPA: 0.04, defEPA:  0.00, passRate: 0.63 },
  { name: 'Seattle Seahawks',     rating: 2.0,  pace: 62, offEPA: 0.02, defEPA:  0.01, passRate: 0.58 },
  { name: 'Pittsburgh Steelers',  rating: 2.2,  pace: 60, offEPA: 0.01, defEPA: -0.05, passRate: 0.55 },
  { name: 'Jacksonville Jaguars', rating: 1.5,  pace: 63, offEPA: 0.02, defEPA:  0.03, passRate: 0.60 },
  { name: 'Atlanta Falcons',      rating: 1.0,  pace: 62, offEPA: 0.01, defEPA:  0.02, passRate: 0.56 },
  { name: 'Tampa Bay Buccaneers', rating: 1.2,  pace: 63, offEPA: 0.02, defEPA:  0.01, passRate: 0.60 },
  { name: 'Indianapolis Colts',   rating: 0.5,  pace: 62, offEPA: 0.00, defEPA:  0.02, passRate: 0.57 },
  { name: 'Chicago Bears',        rating: 0.0,  pace: 61, offEPA: -0.01, defEPA: 0.00, passRate: 0.55 },
  { name: 'New Orleans Saints',   rating: -0.5, pace: 62, offEPA: -0.02, defEPA: 0.03, passRate: 0.58 },
  { name: 'Cleveland Browns',     rating: -0.8, pace: 60, offEPA: -0.04, defEPA: -0.02, passRate: 0.56 },
  { name: 'Washington Commanders',rating: -1.0, pace: 63, offEPA: -0.03, defEPA: 0.04, passRate: 0.58 },
  { name: 'Arizona Cardinals',    rating: -1.5, pace: 62, offEPA: -0.05, defEPA: 0.03, passRate: 0.57 },
  { name: 'Denver Broncos',       rating: -2.0, pace: 60, offEPA: -0.06, defEPA: 0.00, passRate: 0.55 },
  { name: 'New York Jets',        rating: -2.2, pace: 61, offEPA: -0.07, defEPA:-0.03, passRate: 0.56 },
  { name: 'Tennessee Titans',     rating: -2.5, pace: 60, offEPA: -0.08, defEPA: 0.04, passRate: 0.53 },
  { name: 'Las Vegas Raiders',    rating: -3.0, pace: 61, offEPA: -0.09, defEPA: 0.05, passRate: 0.58 },
  { name: 'New England Patriots', rating: -3.5, pace: 60, offEPA: -0.10, defEPA: 0.02, passRate: 0.54 },
  { name: 'New York Giants',      rating: -4.0, pace: 61, offEPA: -0.11, defEPA: 0.05, passRate: 0.55 },
  { name: 'Carolina Panthers',    rating: -5.0, pace: 60, offEPA: -0.13, defEPA: 0.07, passRate: 0.56 },
]

/* Normal CDF via Abramowitz & Stegun approximation */
function normCdf(x) {
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911
  const sign = x < 0 ? -1 : 1
  x = Math.abs(x) / Math.sqrt(2)
  const t = 1.0 / (1.0 + p * x)
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x)
  return 0.5 * (1.0 + sign * y)
}

function fmtPct(p) {
  return `${(p * 100).toFixed(1)}%`
}

function confidenceLabel(p) {
  const edge = Math.abs(p - 0.5)
  if (edge >= 0.35) return { label: 'LOCK', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/40' }
  if (edge >= 0.22) return { label: 'HIGH', color: 'text-lime-400',    bg: 'bg-lime-500/10 border-lime-500/40' }
  if (edge >= 0.12) return { label: 'LEAN', color: 'text-yellow-400',  bg: 'bg-yellow-500/10 border-yellow-500/40' }
  return { label: 'PASS', color: 'text-gray-400', bg: 'bg-gray-500/10 border-gray-500/40' }
}

function analyze({ home, away, homeInjuries, awayInjuries, weatherWind, weatherRain, isDome, homeQBOut, awayQBOut, restEdgeHome }) {
  /* HFA: ~2 pts standard */
  const hfa = 2.0
  const injuryAdj = (awayInjuries - homeInjuries) * 0.4
  const qbAdj = (awayQBOut ? 5.5 : 0) - (homeQBOut ? 5.5 : 0)
  const restAdj = restEdgeHome * 0.3

  const spreadHome = -(home.rating - away.rating + hfa + injuryAdj + qbAdj + restAdj)
  const modelMargin = -spreadHome

  /* Win prob: sigma ~ 13.86 in NFL margin distribution */
  const sigma = 13.86
  const homeWinProb = 1 - normCdf(-modelMargin / sigma)
  const awayWinProb = 1 - homeWinProb

  /* Total points model */
  const baseTotal = 44.5
  const paceMod = ((home.pace + away.pace) / 2 - 62) * 0.3
  const epaMod = (home.offEPA + away.offEPA) * 40 - (home.defEPA + away.defEPA) * 30
  let projectedTotal = baseTotal + paceMod + epaMod
  if (!isDome) {
    if (weatherWind > 15) projectedTotal -= (weatherWind - 15) * 0.4
    if (weatherRain)      projectedTotal -= 3.5
  }
  if (homeQBOut) projectedTotal -= 4
  if (awayQBOut) projectedTotal -= 4

  const homeScore = projectedTotal / 2 + modelMargin / 2
  const awayScore = projectedTotal / 2 - modelMargin / 2

  /* Market probabilities */
  const totalSigma = 10.5
  const overProb  = 1 - normCdf((projectedTotal - projectedTotal) / totalSigma) // vs itself = 0.5 baseline
  // Compute for common lines
  const commonTotals = [40.5, 42.5, 44.5, 46.5, 48.5, 50.5]
  const totalMarkets = commonTotals.map(line => {
    const p = 1 - normCdf((line - projectedTotal) / totalSigma)
    return { line, overProb: p, underProb: 1 - p }
  })

  const commonSpreads = [-10.5, -7.5, -6.5, -3.5, -2.5, 1.5, 2.5, 3.5, 6.5, 7.5, 10.5]
  const spreadMarkets = commonSpreads.map(line => {
    // Prob home covers line: P(home_margin > line) = P((margin - modelMargin)/sigma > (line - modelMargin)/sigma)
    const p = 1 - normCdf((line - modelMargin) / sigma)
    return { line, homeCoverProb: p, awayCoverProb: 1 - p }
  })

  /* Props — simplified projections */
  const homePassYds = 220 + home.offEPA * 200 + home.passRate * 100 - (weatherWind > 20 ? 25 : 0) - (homeQBOut ? 60 : 0)
  const awayPassYds = 220 + away.offEPA * 200 + away.passRate * 100 - (weatherWind > 20 ? 25 : 0) - (awayQBOut ? 60 : 0)
  const homeRushYds = 110 - home.offEPA * 30 + (1 - home.passRate) * 80
  const awayRushYds = 110 - away.offEPA * 30 + (1 - away.passRate) * 80

  return {
    spreadHome, modelMargin, homeWinProb, awayWinProb,
    projectedTotal, homeScore, awayScore,
    totalMarkets, spreadMarkets,
    homePassYds, awayPassYds, homeRushYds, awayRushYds,
    fairML: {
      home: homeWinProb >= 0.5 ? -Math.round(100 * homeWinProb / (1 - homeWinProb)) : Math.round(100 * (1 - homeWinProb) / homeWinProb),
      away: awayWinProb >= 0.5 ? -Math.round(100 * awayWinProb / (1 - awayWinProb)) : Math.round(100 * (1 - awayWinProb) / awayWinProb),
    }
  }
}

export default function FootballAnalyzer() {
  const [homeName, setHomeName] = useState('Kansas City Chiefs')
  const [awayName, setAwayName] = useState('Buffalo Bills')
  const [homeInjuries, setHomeInjuries] = useState(1)
  const [awayInjuries, setAwayInjuries] = useState(1)
  const [weatherWind, setWeatherWind] = useState(5)
  const [weatherRain, setWeatherRain] = useState(false)
  const [isDome, setIsDome] = useState(false)
  const [homeQBOut, setHomeQBOut] = useState(false)
  const [awayQBOut, setAwayQBOut] = useState(false)
  const [restEdgeHome, setRestEdgeHome] = useState(0)

  const home = DEFAULT_TEAMS.find(t => t.name === homeName) || DEFAULT_TEAMS[0]
  const away = DEFAULT_TEAMS.find(t => t.name === awayName) || DEFAULT_TEAMS[1]

  const result = useMemo(() => analyze({
    home, away, homeInjuries, awayInjuries, weatherWind, weatherRain, isDome, homeQBOut, awayQBOut, restEdgeHome
  }), [home, away, homeInjuries, awayInjuries, weatherWind, weatherRain, isDome, homeQBOut, awayQBOut, restEdgeHome])

  const homeConf = confidenceLabel(result.homeWinProb)
  const awayConf = confidenceLabel(result.awayWinProb)

  const topPicks = useMemo(() => {
    const picks = []
    picks.push({
      market: 'Moneyline',
      pick: result.homeWinProb > result.awayWinProb ? `${homeName} ML` : `${awayName} ML`,
      prob: Math.max(result.homeWinProb, result.awayWinProb),
    })
    result.spreadMarkets.forEach(s => {
      picks.push({
        market: `Spread ${s.line > 0 ? '+' : ''}${s.line}`,
        pick: s.homeCoverProb > s.awayCoverProb ? `${homeName} ${s.line > 0 ? '+' : ''}${s.line}` : `${awayName} ${-s.line > 0 ? '+' : ''}${-s.line}`,
        prob: Math.max(s.homeCoverProb, s.awayCoverProb),
      })
    })
    result.totalMarkets.forEach(t => {
      picks.push({
        market: `Total ${t.line}`,
        pick: t.overProb > t.underProb ? `Over ${t.line}` : `Under ${t.line}`,
        prob: Math.max(t.overProb, t.underProb),
      })
    })
    return picks.sort((a, b) => b.prob - a.prob).slice(0, 8)
  }, [result, homeName, awayName])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-black text-white">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <Link to="/" className="text-purple-400 hover:text-purple-300 text-sm">← Home</Link>
          <div className="text-xs text-gray-500">For entertainment. 21+. Bet responsibly.</div>
        </div>

        <header className="mb-8">
          <h1 className="text-4xl md:text-5xl font-black bg-gradient-to-r from-emerald-400 via-lime-400 to-yellow-400 bg-clip-text text-transparent">
            NFL Aggressive Match Analyzer
          </h1>
          <p className="text-gray-400 mt-2">Power-rating + EPA + situational model. Outputs win, spread, total & prop probabilities with confidence tiers.</p>
        </header>

        {/* Inputs */}
        <div className="grid md:grid-cols-2 gap-4 bg-gray-900/60 rounded-2xl p-6 border border-gray-800 mb-6">
          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Home Team</label>
            <select value={homeName} onChange={e => setHomeName(e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2">
              {DEFAULT_TEAMS.map(t => <option key={t.name}>{t.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Away Team</label>
            <select value={awayName} onChange={e => setAwayName(e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2">
              {DEFAULT_TEAMS.map(t => <option key={t.name}>{t.name}</option>)}
            </select>
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Home Key Injuries (0–5)</label>
            <input type="number" min="0" max="5" value={homeInjuries} onChange={e => setHomeInjuries(+e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Away Key Injuries (0–5)</label>
            <input type="number" min="0" max="5" value={awayInjuries} onChange={e => setAwayInjuries(+e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2" />
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Wind (mph)</label>
            <input type="number" min="0" max="40" value={weatherWind} onChange={e => setWeatherWind(+e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-gray-400">Home Rest Advantage (days)</label>
            <input type="number" min="-7" max="7" value={restEdgeHome} onChange={e => setRestEdgeHome(+e.target.value)} className="w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2" />
          </div>

          <div className="flex flex-wrap gap-4 md:col-span-2 pt-2">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isDome} onChange={e => setIsDome(e.target.checked)} /> Dome / Retractable Closed</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={weatherRain} onChange={e => setWeatherRain(e.target.checked)} /> Heavy Rain / Snow</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={homeQBOut} onChange={e => setHomeQBOut(e.target.checked)} /> Home QB1 OUT</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={awayQBOut} onChange={e => setAwayQBOut(e.target.checked)} /> Away QB1 OUT</label>
          </div>
        </div>

        {/* Headline */}
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <div className={`rounded-2xl p-6 border ${homeConf.bg}`}>
            <div className="text-xs text-gray-400">HOME WIN</div>
            <div className="text-2xl font-bold">{homeName}</div>
            <div className="text-5xl font-black mt-2">{fmtPct(result.homeWinProb)}</div>
            <div className={`text-sm mt-2 font-bold ${homeConf.color}`}>{homeConf.label}</div>
            <div className="text-xs text-gray-500 mt-1">Fair ML: {result.fairML.home > 0 ? '+' : ''}{result.fairML.home}</div>
          </div>
          <div className="rounded-2xl p-6 border border-gray-800 bg-gray-900/60">
            <div className="text-xs text-gray-400">PROJECTED SCORE</div>
            <div className="text-3xl font-bold mt-2">
              {result.homeScore.toFixed(1)} <span className="text-gray-500">—</span> {result.awayScore.toFixed(1)}
            </div>
            <div className="text-xs text-gray-400 mt-2">Model spread: {homeName} {result.spreadHome > 0 ? '+' : ''}{result.spreadHome.toFixed(1)}</div>
            <div className="text-xs text-gray-400">Projected total: {result.projectedTotal.toFixed(1)}</div>
          </div>
          <div className={`rounded-2xl p-6 border ${awayConf.bg}`}>
            <div className="text-xs text-gray-400">AWAY WIN</div>
            <div className="text-2xl font-bold">{awayName}</div>
            <div className="text-5xl font-black mt-2">{fmtPct(result.awayWinProb)}</div>
            <div className={`text-sm mt-2 font-bold ${awayConf.color}`}>{awayConf.label}</div>
            <div className="text-xs text-gray-500 mt-1">Fair ML: {result.fairML.away > 0 ? '+' : ''}{result.fairML.away}</div>
          </div>
        </div>

        {/* Top Picks */}
        <div className="bg-gradient-to-br from-emerald-900/30 to-gray-900/60 rounded-2xl p-6 border border-emerald-500/30 mb-6">
          <h2 className="text-xl font-bold mb-4">🔥 Top 8 Aggressive Picks (Highest Probability)</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {topPicks.map((p, i) => {
              const c = confidenceLabel(p.prob)
              return (
                <div key={i} className={`flex items-center justify-between p-3 rounded-lg border ${c.bg}`}>
                  <div>
                    <div className="text-xs text-gray-400">{p.market}</div>
                    <div className="font-bold">{p.pick}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black">{fmtPct(p.prob)}</div>
                    <div className={`text-xs font-bold ${c.color}`}>{c.label}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Spreads */}
        <div className="bg-gray-900/60 rounded-2xl p-6 border border-gray-800 mb-6">
          <h2 className="text-xl font-bold mb-4">Spread Market Probabilities</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-400 text-xs uppercase">
                <tr><th className="text-left py-2">Home Line</th><th>Home Covers</th><th>Away Covers</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                {result.spreadMarkets.map((s, i) => {
                  const p = Math.max(s.homeCoverProb, s.awayCoverProb)
                  const c = confidenceLabel(p)
                  return (
                    <tr key={i} className="border-t border-gray-800">
                      <td className="py-2 font-mono">{homeName} {s.line > 0 ? '+' : ''}{s.line}</td>
                      <td className="text-center">{fmtPct(s.homeCoverProb)}</td>
                      <td className="text-center">{fmtPct(s.awayCoverProb)}</td>
                      <td className={`text-center font-bold ${c.color}`}>{c.label}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Totals */}
        <div className="bg-gray-900/60 rounded-2xl p-6 border border-gray-800 mb-6">
          <h2 className="text-xl font-bold mb-4">Totals Market Probabilities</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-400 text-xs uppercase">
                <tr><th className="text-left py-2">Line</th><th>Over</th><th>Under</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                {result.totalMarkets.map((t, i) => {
                  const p = Math.max(t.overProb, t.underProb)
                  const c = confidenceLabel(p)
                  return (
                    <tr key={i} className="border-t border-gray-800">
                      <td className="py-2 font-mono">{t.line}</td>
                      <td className="text-center">{fmtPct(t.overProb)}</td>
                      <td className="text-center">{fmtPct(t.underProb)}</td>
                      <td className={`text-center font-bold ${c.color}`}>{c.label}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Props / Stats */}
        <div className="bg-gray-900/60 rounded-2xl p-6 border border-gray-800 mb-10">
          <h2 className="text-xl font-bold mb-4">Team Stat Projections (for player props)</h2>
          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
              <div className="font-bold text-lg mb-2">{homeName}</div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Team Pass Yards</span><span className="font-mono">{result.homePassYds.toFixed(0)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Team Rush Yards</span><span className="font-mono">{result.homeRushYds.toFixed(0)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Projected Points</span><span className="font-mono">{result.homeScore.toFixed(1)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Pass Rate</span><span className="font-mono">{(home.passRate * 100).toFixed(0)}%</span></div>
            </div>
            <div className="p-4 rounded-lg bg-gray-800/50 border border-gray-700">
              <div className="font-bold text-lg mb-2">{awayName}</div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Team Pass Yards</span><span className="font-mono">{result.awayPassYds.toFixed(0)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Team Rush Yards</span><span className="font-mono">{result.awayRushYds.toFixed(0)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Projected Points</span><span className="font-mono">{result.awayScore.toFixed(1)}</span></div>
              <div className="flex justify-between py-1"><span className="text-gray-400">Pass Rate</span><span className="font-mono">{(away.passRate * 100).toFixed(0)}%</span></div>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-4">
            Confidence tiers — LOCK ≥85%, HIGH ≥72%, LEAN ≥62%, PASS &lt;62%. Model uses power ratings, EPA, pace, HFA, injuries, weather & rest. Always shop lines and manage bankroll.
          </div>
        </div>
      </div>
    </div>
  )
}
