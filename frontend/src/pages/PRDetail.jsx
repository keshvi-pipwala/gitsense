import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import PRAnalysisCard from '../components/pr/PRAnalysisCard'

export default function PRDetail() {
  const { id } = useParams()
  const [pr, setPR] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getPR(id)
      .then(setPR)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="p-6 space-y-4">
      {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
    </div>
  )

  if (error) return (
    <div className="p-6">
      <div className="card border-risk-high text-risk-high text-center py-12">
        <p className="text-xl mb-2">⚠️ {error}</p>
        <Link to="/prs" className="btn-ghost mt-4 inline-block">← Back to PRs</Link>
      </div>
    </div>
  )

  return (
    <div className="p-6 space-y-4">
      <Link to="/prs" className="text-sm text-slate-500 hover:text-accent transition-colors">← Back to PR Intelligence</Link>
      <PRAnalysisCard pr={pr} />
    </div>
  )
}
