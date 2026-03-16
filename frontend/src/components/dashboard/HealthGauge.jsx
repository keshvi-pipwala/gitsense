import { healthColor } from '../../lib/utils'

export default function HealthGauge({ score = 0, size = 180 }) {
  const radius = 70
  const circumference = Math.PI * radius  // half circle
  const offset = circumference - (score / 100) * circumference
  const color = healthColor(score)
  const cx = size / 2
  const cy = size * 0.72

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.6} viewBox={`0 0 ${size} ${size * 0.6}`}>
        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="#334155"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          className="gauge-arc"
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            '--target-offset': offset,
            filter: `drop-shadow(0 0 8px ${color}60)`,
            transition: 'stroke-dashoffset 1.5s cubic-bezier(0.4,0,0.2,1)',
          }}
        />
        {/* Score text */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fill={color}
          fontSize="32"
          fontWeight="700"
          fontFamily="Inter, sans-serif"
        >
          {Math.round(score)}
        </text>
        <text
          x={cx}
          y={cy + 14}
          textAnchor="middle"
          fill="#64748b"
          fontSize="11"
          fontFamily="Inter, sans-serif"
        >
          HEALTH SCORE
        </text>
        {/* Min/Max labels */}
        <text x={cx - radius} y={cy + 22} textAnchor="middle" fill="#475569" fontSize="10">0</text>
        <text x={cx + radius} y={cy + 22} textAnchor="middle" fill="#475569" fontSize="10">100</text>
      </svg>
    </div>
  )
}
