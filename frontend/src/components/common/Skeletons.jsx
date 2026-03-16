import clsx from 'clsx'

export function Skeleton({ className }) {
  return <div className={clsx('skeleton', className)} />
}

export function CardSkeleton({ lines = 3 }) {
  return (
    <div className="card space-y-3 animate-pulse">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function PRCardSkeleton() {
  return (
    <div className="card flex items-start gap-4 animate-pulse">
      <Skeleton className="w-10 h-10 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="flex gap-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-16 rounded-full" />
        </div>
        <Skeleton className="h-3 w-full" />
        <div className="flex gap-3">
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="card space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 py-1">
          <Skeleton className="h-3 w-1/3" />
          <Skeleton className="h-3 w-16 ml-auto" />
        </div>
      ))}
    </div>
  )
}
