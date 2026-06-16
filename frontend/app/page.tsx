'use client'
import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

type Stage = 'upload' | 'processing' | 'result' | 'error'

interface Source {
  rank: number; source_name: string; section: string; url: string
  passage_preview: string; similarity_score: number; relevance_label: string
}
interface Analysis {
  summary: string; explanation: string
  deadlines: { date: string; description: string; urgency: string }[]
  required_actions: string[]; confidence_rationale: string
  disclaimer: string; guard_rail_triggered?: boolean
}
interface Result {
  document_id: string; doc_type: string; out_of_scope?: boolean; message?: string
  analysis?: Analysis
  explainability?: { confidence_score: number; confidence_percent: string; retrieved_sources: Source[]; reasoning_summary: string; guard_rail_triggered: boolean }
}

const DOC_TYPE_LABELS: Record<string, string> = {
  appointment_letter: 'Appointment Letter',
  documentation_request: 'Documentation Request',
  extension_notice: 'Extension Notice',
  out_of_scope: 'Out of Scope',
  unknown: 'Unknown Document',
}

function ThemeToggle({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <button onClick={toggle} aria-label="Toggle dark mode"
      className="relative w-14 h-7 rounded-full border-2 transition-all duration-300 focus:outline-none border-gray-600 bg-gray-800 dark:border-gray-300 dark:bg-white">
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full transition-all duration-300 flex items-center justify-center text-xs
        ${dark ? 'translate-x-7 bg-gray-900' : 'translate-x-0 bg-yellow-400'}`}>
        {dark ? '🌙' : '☀️'}
      </span>
    </button>
  )
}

function Logo({ dark }: { dark: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 flex-shrink-0">
        <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
          <rect width="40" height="40" rx="10" fill={dark ? 'white' : '#111'}/>
          <rect x="8" y="9" width="15" height="2.5" rx="1.25" fill={dark ? '#111' : 'white'}/>
          <rect x="8" y="15" width="24" height="2.5" rx="1.25" fill={dark ? '#111' : 'white'}/>
          <rect x="8" y="21" width="19" height="2.5" rx="1.25" fill={dark ? '#111' : 'white'}/>
          <rect x="8" y="27" width="11" height="2.5" rx="1.25" fill={dark ? '#111' : 'white'}/>
          <circle cx="30" cy="29" r="7" fill={dark ? '#111' : 'white'}/>
          <path d="M27 29l2.2 2.2 4.4-4.4" stroke={dark ? 'white' : '#111'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div>
        <div className="font-bold text-xl leading-tight tracking-tight text-white">DocAssist</div>
        <div className="text-gray-400 text-xs leading-tight font-light tracking-wide">Immigration · Explainable AI · RAG</div>
      </div>
    </div>
  )
}

function StepBar({ stage }: { stage: Stage }) {
  const idx = stage === 'upload' ? 0 : stage === 'processing' ? 1 : 2
  const steps = ['Upload', 'Analysis', 'Results']
  return (
    <div className="flex items-center justify-center gap-0 py-6">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center">
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all duration-300
              ${i < idx ? 'bg-gray-900 border-gray-900 text-white dark:bg-white dark:border-white dark:text-gray-900'
                : i === idx ? 'bg-white border-gray-900 text-gray-900 dark:bg-gray-900 dark:border-white dark:text-white'
                : 'bg-white border-gray-300 text-gray-400 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-500'}`}>
              {i < idx ? '✓' : i + 1}
            </div>
            <span className={`text-xs mt-1.5 font-medium tracking-wide
              ${i === idx ? 'text-gray-900 dark:text-white' : 'text-gray-400 dark:text-gray-500'}`}>{s}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`w-16 h-0.5 mx-3 mb-5 transition-all duration-300
              ${i < idx ? 'bg-gray-900 dark:bg-white' : 'bg-gray-200 dark:bg-gray-700'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

export default function Home() {
  const [dark, setDark] = useState(false)
  const [stage, setStage] = useState<Stage>('upload')
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'explanation' | 'sources' | 'feedback'>('explanation')
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [feedbackSent, setFeedbackSent] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark') { setDark(true); document.documentElement.classList.add('dark') }
  }, [])

  const toggleTheme = () => {
    const next = !dark; setDark(next)
    if (next) { document.documentElement.classList.add('dark'); localStorage.setItem('theme', 'dark') }
    else { document.documentElement.classList.remove('dark'); localStorage.setItem('theme', 'light') }
  }

  const handleFile = useCallback((f: File) => setFile(f), [])
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]; if (f) handleFile(f)
  }

  const handleAnalyse = async () => {
    if (!file) return
    setStage('processing'); setError('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const up = await axios.post('/api/v1/upload', fd)
      const an = await axios.post(`/api/v1/analyze/${up.data.document_id}`)
      setResult(an.data); setStage('result')
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Something went wrong.')
      setStage('error')
    }
  }

  const sendFeedback = async () => {
    if (!result || rating === 0) return
    await axios.post('/api/v1/feedback', { analysis_id: result.document_id, rating, comment }).catch(() => {})
    setFeedbackSent(true)
  }

  const reset = () => {
    setStage('upload'); setFile(null); setResult(null)
    setError(''); setRating(0); setComment(''); setFeedbackSent(false); setActiveTab('explanation')
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-950 transition-colors duration-300 overflow-x-hidden">

      {/* HEADER */}
      <header className="bg-black dark:bg-gray-900 border-b border-gray-800 px-4 sm:px-6 py-4 sticky top-0 z-30 shadow-md w-full">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Logo dark={dark} />
          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle dark={dark} toggle={toggleTheme} />
            {stage !== 'upload' && (
              <button onClick={reset}
                className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-400 px-3 py-2 rounded-lg transition-all">
                ← New
              </button>
            )}
            <span className="hidden sm:block text-xs bg-gray-800 text-gray-400 px-3 py-1.5 rounded-lg font-mono border border-gray-700">
              BM25 + Claude
            </span>
          </div>
        </div>
      </header>

      {/* HERO — upload stage only */}
      {stage === 'upload' && (
        <div className="w-full relative">
          {/* Background image fixed height */}
          <div className="absolute inset-0 z-0 overflow-hidden">
            <img
              src="https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1600&q=80"
              alt="Law background"
              className="w-full h-full object-cover object-center"
            />
            <div className={`absolute inset-0 transition-all duration-300 ${dark
              ? 'bg-gradient-to-b from-gray-950/95 via-gray-950/90 to-gray-950'
              : 'bg-gradient-to-b from-black/90 via-black/80 to-black/65'}`} />
          </div>
          <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 pt-12 pb-20 text-center">
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 text-white/80 text-xs px-4 py-1.5 rounded-full mb-5 backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              MSc AI Thesis · Explainable RAG System
            </div>
            <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4 leading-tight">
              Understand Your<br />
              <span className="text-gray-300">Immigration Documents</span>
            </h1>
            <p className="text-gray-400 text-sm sm:text-base max-w-xl mx-auto leading-relaxed px-2">
              Upload a German residence permit document and receive a plain-language
              explanation grounded in official legal sources — with full source transparency.
            </p>
            <div className="grid grid-cols-3 gap-2 sm:gap-3 mt-8 max-w-2xl mx-auto">
              {[
                { label: 'Appointment Letter', de: 'Termineinladung', icon: '📅' },
                { label: 'Documentation Request', de: 'Nachforderung', icon: '📋' },
                { label: 'Extension Notice', de: 'Verlängerungshinweis', icon: '🔄' },
              ].map(t => (
                <div key={t.label} className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl p-3 sm:p-4 text-center hover:bg-white/15 transition-all">
                  <div className="text-xl sm:text-2xl mb-1 sm:mb-2">{t.icon}</div>
                  <div className="text-white text-xs font-semibold leading-tight">{t.label}</div>
                  <div className="text-gray-300 text-xs mt-0.5 hidden sm:block">{t.de}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* MAIN */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 pb-12">

        {/* UPLOAD */}
        {stage === 'upload' && (
          <div className="space-y-4 -mt-10 relative z-10">
            <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-800 overflow-hidden">
              <div className="p-5 sm:p-6 border-b border-gray-100 dark:border-gray-800">
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">Upload Document</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">PDF, JPG, or PNG · Max 10 MB</p>
              </div>
              <div className="p-5 sm:p-6">
                <div
                  onDragOver={e => { e.preventDefault(); setDragging(true) }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  onClick={() => document.getElementById('file-input')?.click()}
                  className={`border-2 border-dashed rounded-xl p-8 sm:p-10 text-center cursor-pointer transition-all
                    ${dragging
                      ? 'border-black dark:border-white bg-gray-50 dark:bg-gray-800 scale-[1.01]'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800'}`}
                >
                  <input id="file-input" type="file" className="hidden"
                    accept=".pdf,.jpg,.jpeg,.png,.tiff"
                    onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
                  <div className="w-12 h-12 sm:w-14 sm:h-14 mx-auto mb-4 rounded-2xl bg-black dark:bg-white flex items-center justify-center shadow-lg">
                    <svg className="w-6 h-6 sm:w-7 sm:h-7 text-white dark:text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                        d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p className="text-gray-800 dark:text-gray-200 font-semibold text-sm sm:text-base">Drop your document here</p>
                  <p className="text-gray-400 dark:text-gray-500 text-xs sm:text-sm mt-1">or click to browse your files</p>
                </div>

                {file && (
                  <div className="mt-4 bg-gray-950 dark:bg-gray-800 rounded-xl p-4 flex items-center justify-between gap-3 border border-gray-800 dark:border-gray-700">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 bg-gray-700 rounded-xl flex items-center justify-center text-white text-xs font-bold uppercase flex-shrink-0">
                        {file.name.split('.').pop()}
                      </div>
                      <div className="min-w-0">
                        <div className="text-white text-sm font-medium truncate">{file.name}</div>
                        <div className="text-gray-400 text-xs">{(file.size / 1024).toFixed(0)} KB · Ready to analyse</div>
                      </div>
                    </div>
                    <button onClick={handleAnalyse}
                      className="bg-white hover:bg-gray-100 text-black px-4 py-2.5 rounded-xl font-bold text-sm transition-all shadow-md flex-shrink-0">
                      Analyse →
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex gap-3">
              <span className="text-lg flex-shrink-0">⚖️</span>
              <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                <strong>Legal Disclaimer:</strong> This tool provides plain-language explanations for informational purposes only
                and does not constitute legal advice. Always consult a licensed immigration lawyer or your local Ausländerbehörde.
              </p>
            </div>
          </div>
        )}

        {/* PROCESSING */}
        {stage === 'processing' && (
          <div className="flex flex-col items-center justify-center py-20 space-y-8">
            <div className="relative w-20 h-20 sm:w-24 sm:h-24">
              <div className="absolute inset-0 rounded-full border-4 border-gray-200 dark:border-gray-700" />
              <div className="absolute inset-0 rounded-full border-4 border-black dark:border-white border-t-transparent animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center">
                <svg className="w-8 h-8 sm:w-9 sm:h-9 text-black dark:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z" />
                </svg>
              </div>
            </div>
            <div className="text-center">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">Analysing document…</h2>
              <p className="text-gray-400 text-sm mt-1">Retrieving legal sources and generating explanation</p>
            </div>
            <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl p-5 sm:p-6 w-full max-w-sm shadow-sm space-y-4">
              {[
                { label: 'Extracting text (OCR)', done: true },
                { label: 'Classifying document type', done: true },
                { label: 'Retrieving law passages (BM25)', done: true },
                { label: 'Generating explanation (Claude)', done: false },
              ].map(({ label, done }, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold
                    ${done ? 'bg-black dark:bg-white text-white dark:text-black' : 'border-2 border-gray-300 dark:border-gray-600 animate-pulse'}`}>
                    {done ? '✓' : ''}
                  </div>
                  <span className={`text-sm ${done ? 'text-gray-900 dark:text-white font-medium' : 'text-gray-400'}`}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ERROR */}
        {stage === 'error' && (
          <div className="mt-6">
            <StepBar stage="upload" />
            <div className="bg-white dark:bg-gray-900 border-2 border-red-100 dark:border-red-900 rounded-2xl p-8 sm:p-10 text-center space-y-4 shadow-sm">
              <div className="w-14 h-14 sm:w-16 sm:h-16 mx-auto bg-red-50 dark:bg-red-950 border-2 border-red-200 dark:border-red-800 rounded-full flex items-center justify-center text-2xl sm:text-3xl">⚠️</div>
              <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white">Analysis Failed</h2>
              <p className="text-red-600 dark:text-red-400 text-sm max-w-sm mx-auto bg-red-50 dark:bg-red-950/50 rounded-lg px-4 py-2">{error}</p>
              <button onClick={reset} className="bg-black dark:bg-white text-white dark:text-black px-6 py-3 rounded-xl text-sm font-semibold hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors shadow-md">
                Try Again
              </button>
            </div>
          </div>
        )}

        {/* RESULT */}
        {stage === 'result' && result && (
          <div className="space-y-4 mt-2">
            <StepBar stage="result" />

            {result.out_of_scope && (
              <div className="bg-white dark:bg-gray-900 border-2 border-gray-900 dark:border-gray-600 rounded-2xl p-5 sm:p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 sm:w-11 sm:h-11 bg-black dark:bg-white rounded-full flex items-center justify-center text-white dark:text-black text-lg flex-shrink-0">🚫</div>
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-gray-900 dark:text-white">Outside Supported Scope</h2>
                    <p className="text-xs text-gray-400">This document type is not covered by the system</p>
                  </div>
                </div>
                <p className="text-gray-600 dark:text-gray-400 text-sm">{result.message}</p>
              </div>
            )}

            {!result.out_of_scope && result.analysis && (
              <>
                {/* Result header */}
                <div className="bg-gray-950 dark:bg-gray-900 border dark:border-gray-700 rounded-2xl p-4 sm:p-5 flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-800 rounded-xl flex items-center justify-center text-lg">
                      {result.doc_type === 'appointment_letter' ? '📅' : result.doc_type === 'documentation_request' ? '📋' : '🔄'}
                    </div>
                    <div>
                      <div className="text-white font-semibold text-sm">{DOC_TYPE_LABELS[result.doc_type] || result.doc_type}</div>
                      <div className="text-gray-500 text-xs">Analysis complete</div>
                    </div>
                  </div>
                  {result.explainability && (
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-xs text-gray-500">Source confidence</div>
                        <div className={`text-lg font-bold ${result.explainability.confidence_score > 0.6 ? 'text-green-400' : result.explainability.confidence_score > 0.3 ? 'text-amber-400' : 'text-red-400'}`}>
                          {result.explainability.confidence_percent}
                        </div>
                      </div>
                      <div className={`w-2 h-10 rounded-full ${result.explainability.confidence_score > 0.6 ? 'bg-green-400' : result.explainability.confidence_score > 0.3 ? 'bg-amber-400' : 'bg-red-400'}`} />
                    </div>
                  )}
                </div>

                {/* Summary */}
                <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-5 rounded-full bg-black dark:bg-white" />
                    <p className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-widest">Summary</p>
                  </div>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm">{result.analysis.summary}</p>
                </div>

                {/* Deadlines */}
                {result.analysis.deadlines?.length > 0 && (
                  <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-5 sm:p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-1 h-5 rounded-full bg-red-500" />
                      <p className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-widest">Important Deadlines</p>
                    </div>
                    <div className="space-y-3">
                      {result.analysis.deadlines.map((d, i) => (
                        <div key={i} className={`flex gap-3 p-3 rounded-xl ${d.urgency === 'high' ? 'bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900' : 'bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900'}`}>
                          <span className="text-lg flex-shrink-0">{d.urgency === 'high' ? '🔴' : '🟡'}</span>
                          <div>
                            <div className="font-bold text-gray-900 dark:text-white text-sm">{d.date}</div>
                            <div className="text-gray-600 dark:text-gray-400 text-sm">{d.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Required Actions */}
                {result.analysis.required_actions?.length > 0 && (
                  <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-5 sm:p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-1 h-5 rounded-full bg-black dark:bg-white" />
                      <p className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-widest">Required Actions</p>
                    </div>
                    <ol className="space-y-3">
                      {result.analysis.required_actions.map((a, i) => (
                        <li key={i} className="flex gap-3 items-start p-3 bg-gray-50 dark:bg-gray-800 rounded-xl">
                          <span className="w-6 h-6 rounded-full bg-black dark:bg-white text-white dark:text-black flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">{i + 1}</span>
                          <span className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed">{a}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Tabs */}
                <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 overflow-hidden shadow-sm">
                  <div className="flex bg-gray-50 dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700">
                    {(['explanation', 'sources', 'feedback'] as const).map(t => (
                      <button key={t} onClick={() => setActiveTab(t)}
                        className={`flex-1 py-3 text-xs sm:text-sm font-semibold transition-all
                          ${activeTab === t
                            ? 'bg-white dark:bg-gray-900 text-black dark:text-white border-b-2 border-black dark:border-white shadow-sm'
                            : 'text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}>
                        {t === 'explanation' ? '📖 Explanation'
                          : t === 'sources' ? `📚 Sources (${result.explainability?.retrieved_sources?.length || 0})`
                          : '⭐ Feedback'}
                      </button>
                    ))}
                  </div>
                  <div className="p-5 sm:p-6">
                    {activeTab === 'explanation' && (
                      <div className="space-y-4">
                        <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm">{result.analysis.explanation}</p>
                        {result.explainability?.reasoning_summary && (
                          <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 text-xs text-gray-500 dark:text-gray-400 flex gap-3">
                            <span className="text-base flex-shrink-0">🔍</span>
                            <div><strong className="text-gray-700 dark:text-gray-300 block mb-1">Retrieval Reasoning</strong>{result.explainability.reasoning_summary}</div>
                          </div>
                        )}
                      </div>
                    )}
                    {activeTab === 'sources' && result.explainability && (
                      <div className="space-y-3">
                        {result.explainability.retrieved_sources.map((s, i) => (
                          <div key={i} className="border border-gray-100 dark:border-gray-800 rounded-xl p-4 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm transition-all">
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <div className="min-w-0">
                                <div className="font-bold text-gray-900 dark:text-white text-sm truncate">{s.source_name}</div>
                                <div className="text-xs text-gray-400">{s.section}</div>
                              </div>
                              <span className={`text-xs px-2 py-1 rounded-full border font-medium flex-shrink-0 ${
                                s.relevance_label === 'High' ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950/50 dark:text-green-400'
                                : s.relevance_label === 'Medium' ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400'
                                : 'border-gray-200 bg-gray-50 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400'}`}>
                                {s.relevance_label}
                              </span>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 italic leading-relaxed border-l-2 border-gray-200 dark:border-gray-700 pl-3">{s.passage_preview}</p>
                            {s.url && (
                              <a href={s.url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-black dark:text-white font-medium mt-3 hover:underline underline-offset-2">
                                View official source ↗
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {activeTab === 'feedback' && (
                      <div className="space-y-5">
                        {feedbackSent ? (
                          <div className="text-center py-8">
                            <div className="w-14 h-14 mx-auto bg-black dark:bg-white rounded-full flex items-center justify-center text-white dark:text-black text-2xl mb-4">✓</div>
                            <p className="font-bold text-gray-900 dark:text-white text-lg">Thank you!</p>
                            <p className="text-sm text-gray-400 mt-1">Your feedback helps improve the system.</p>
                          </div>
                        ) : (
                          <>
                            <div>
                              <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-3">How helpful was this explanation?</p>
                              <div className="flex gap-2">
                                {[1,2,3,4,5].map(n => (
                                  <button key={n} onClick={() => setRating(n)}
                                    className={`w-10 h-10 sm:w-11 sm:h-11 rounded-full text-xl transition-all border-2
                                      ${rating >= n
                                        ? 'bg-black dark:bg-white border-black dark:border-white text-white dark:text-black scale-110'
                                        : 'border-gray-200 dark:border-gray-700 text-gray-400 hover:border-gray-400'}`}>
                                    ★
                                  </button>
                                ))}
                              </div>
                            </div>
                            <textarea value={comment} onChange={e => setComment(e.target.value)}
                              placeholder="Share your thoughts on the explanation quality…"
                              className="w-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 rounded-xl p-4 text-sm resize-none h-28 focus:outline-none focus:ring-2 focus:ring-black dark:focus:ring-white transition-all" />
                            <button onClick={sendFeedback} disabled={rating === 0}
                              className="bg-black dark:bg-white text-white dark:text-black px-6 py-3 rounded-xl text-sm font-bold disabled:opacity-30 hover:bg-gray-800 dark:hover:bg-gray-100 transition-all shadow-md">
                              Submit Feedback
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex gap-3">
                  <span className="text-sm flex-shrink-0 mt-0.5">⚖️</span>
                  <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">{result.analysis.disclaimer}</p>
                </div>
              </>
            )}
          </div>
        )}
      </main>

      {/* FOOTER */}
      <footer className="bg-black dark:bg-gray-900 border-t border-gray-800 px-4 sm:px-6 py-5 w-full">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <Logo dark={dark} />
          <div className="text-center sm:text-right">
            <div className="text-gray-500 text-xs">MSc AI Thesis · Kalpana Abhiseka Maddi</div>
            <div className="text-gray-600 text-xs mt-0.5">Explainable RAG · German Residence Permit Documents</div>
          </div>
        </div>
      </footer>
    </div>
  )
}
