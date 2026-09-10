import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Plans from './pages/Plans'
import Success from './pages/Success'
import Portal from './pages/Portal'
import Admin from './pages/Admin'
import FootballAnalyzer from './pages/FootballAnalyzer'
import PageTracker from './PageTracker'

function App() {
  return (
    <BrowserRouter>
      <PageTracker />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/success" element={<Success />} />
        <Route path="/portal" element={<Portal />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/football-analyzer" element={<FootballAnalyzer />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
