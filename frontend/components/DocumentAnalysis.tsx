/**
 * DocumentAnalysis.tsx
 * Main 3-panel analysis page component.
 * Panel 1: Original document viewer
 * Panel 2: Plain-language explanation
 * Panel 3: Explainability panel (sources, confidence, reasoning)
 */

"use client";

import { useState, useEffect } from "react";

interface Deadline {
  date: string;
  description: string;
  urgency: "high" | "normal";
}

interface RetrievedSource {
  rank: number;
  source_name: string;
  section: string;
  url: string;
  passage_preview: string;
  similarity_score: number;
  relevance_label: string;
}

interface Analysis {
  summary: string;
  explanation: string;
  deadlines: Deadline[];
  required_actions: string[];
  confidence_rationale: string;
  disclaimer: string;
}

interface Explainability {
  confidence_score: number;
  confidence_percent: string;
  retrieved_sources: RetrievedSource[];
  reasoning_summary: string;
  guard_rail_triggered: boolean;
  model_used: string;
}

interface AnalysisResult {
  document_id: string;
  doc_type: string;
  analysis: Analysis;
  explainability: Explainability;
  timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DocumentAnalysis({ documentId }: { documentId: string }) {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);

  useEffect(() => {
    if (documentId) runAnalysis();
  }, [documentId]);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/analyze/${documentId}`, { method: "POST" });
      if (!res.ok) throw new Error("Analysis failed. Please try again.");
      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(rating: number) {
    if (!result) return;
    await fetch(`${API_BASE}/api/v1/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: result.document_id, rating }),
    });
    setFeedbackSent(true);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600 text-sm">Analysing your document using official German immigration sources...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 m-4">
      <p className="text-red-700 text-sm">{error}</p>
      <button onClick={runAnalysis} className="mt-2 text-sm text-blue-600 underline">Try again</button>
    </div>
  );

  if (!result) return null;

  const { analysis, explainability } = result;
  const confidenceColor = explainability.confidence_score > 0.85 ? "text-green-600" : explainability.confidence_score > 0.70 ? "text-yellow-600" : "text-red-500";

  return (
    <div className="flex flex-col h-full">
      {/* Guard rail warning */}
      {explainability.guard_rail_triggered && (
        <div className="bg-amber-50 border-l-4 border-amber-400 p-3 mx-4 mt-4 rounded">
          <p className="text-amber-800 text-sm font-medium">
            ⚠️ This query touches on legal advice. The system has provided general information only.
          </p>
        </div>
      )}

      {/* 3-panel grid */}
      <div className="grid grid-cols-3 gap-0 flex-1 min-h-0 border rounded-lg overflow-hidden m-4">

        {/* Panel 1: Summary + Deadlines + Actions */}
        <div className="border-r overflow-y-auto p-4 bg-white">
          <h2 className="text-sm font-bold text-gray-800 mb-3 flex items-center gap-2">
            💬 Plain-Language Explanation
          </h2>

          <div className="bg-blue-50 border-l-4 border-blue-500 rounded p-3 mb-4">
            <p className="text-sm text-gray-700 leading-relaxed">{analysis.summary}</p>
          </div>

          <div className="text-xs text-gray-700 leading-relaxed mb-4 whitespace-pre-line">
            {analysis.explanation}
          </div>

          {/* Deadlines */}
          {analysis.deadlines.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-bold text-gray-600 mb-2 uppercase tracking-wide">⏰ Deadlines</h3>
              {analysis.deadlines.map((d, i) => (
                <div key={i} className={`rounded p-2 mb-2 border ${d.urgency === "high" ? "bg-red-50 border-red-200" : "bg-yellow-50 border-yellow-200"}`}>
                  <p className={`text-sm font-bold ${d.urgency === "high" ? "text-red-700" : "text-amber-700"}`}>{d.date}</p>
                  <p className="text-xs text-gray-700 mt-1">{d.description}</p>
                </div>
              ))}
            </div>
          )}

          {/* Required Actions */}
          {analysis.required_actions.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-bold text-gray-600 mb-2 uppercase tracking-wide">✅ Required Actions</h3>
              {analysis.required_actions.map((action, i) => (
                <div key={i} className="flex items-start gap-2 bg-green-50 border border-green-200 rounded p-2 mb-2">
                  <span className="bg-green-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0 mt-0.5 font-bold">{i + 1}</span>
                  <p className="text-xs text-gray-700">{action}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Panel 2: Explainability */}
        <div className="border-r overflow-y-auto p-4 bg-gray-50">
          <h2 className="text-sm font-bold text-gray-800 mb-3">🔍 Explainability</h2>

          {/* Confidence */}
          <div className="bg-white border rounded p-3 mb-4">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-semibold text-gray-600">Confidence</span>
              <span className={`text-lg font-bold ${confidenceColor}`}>{explainability.confidence_percent}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all"
                style={{ width: explainability.confidence_percent }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-2">{analysis.confidence_rationale}</p>
          </div>

          {/* Reasoning */}
          <div className="bg-white border rounded p-3 mb-4">
            <h3 className="text-xs font-bold text-gray-600 mb-2">Reasoning Summary</h3>
            <p className="text-xs text-gray-600 leading-relaxed">{explainability.reasoning_summary}</p>
          </div>

          {/* Retrieved Sources */}
          <h3 className="text-xs font-bold text-gray-600 mb-2 uppercase tracking-wide">Retrieved Sources</h3>
          {explainability.retrieved_sources.map((src) => (
            <div key={src.rank} className="bg-white border rounded p-3 mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-blue-700">{src.source_name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${src.relevance_label === "High" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                  {src.relevance_label} {src.similarity_score.toFixed(2)}
                </span>
              </div>
              {src.section && <p className="text-xs text-gray-500 mb-1">{src.section}</p>}
              <p className="text-xs text-gray-600 italic leading-relaxed bg-blue-50 p-2 rounded">{src.passage_preview}</p>
              {src.url && (
                <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline mt-1 inline-block">
                  View official source →
                </a>
              )}
            </div>
          ))}
        </div>

        {/* Panel 3: Metadata + Feedback */}
        <div className="overflow-y-auto p-4 bg-white">
          <h2 className="text-sm font-bold text-gray-800 mb-3">ℹ️ Document Info</h2>

          <div className="bg-gray-50 border rounded p-3 mb-4 text-xs text-gray-600 space-y-2">
            <p><span className="font-semibold">Document Type:</span> {result.doc_type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</p>
            <p><span className="font-semibold">Model Used:</span> {explainability.model_used}</p>
            <p><span className="font-semibold">Sources Retrieved:</span> {explainability.retrieved_sources.length}</p>
            <p><span className="font-semibold">Analysed At:</span> {new Date(result.timestamp).toLocaleString()}</p>
          </div>

          {/* Legal Disclaimer */}
          <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
            <p className="text-xs font-bold text-red-700 mb-1">⚠️ Important Disclaimer</p>
            <p className="text-xs text-red-600 leading-relaxed">{analysis.disclaimer}</p>
          </div>

          {/* Feedback */}
          <div className="border rounded p-3">
            <h3 className="text-xs font-bold text-gray-600 mb-2">Was this helpful?</h3>
            {feedbackSent ? (
              <p className="text-xs text-green-600 font-medium">Thank you for your feedback!</p>
            ) : (
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map(r => (
                  <button key={r} onClick={() => sendFeedback(r)}
                    className="text-xl hover:scale-110 transition-transform" title={`Rate ${r}/5`}>
                    {r <= 3 ? "⭐" : r === 4 ? "⭐" : "⭐"}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
