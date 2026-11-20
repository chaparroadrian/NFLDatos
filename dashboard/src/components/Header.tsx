export function Header() {
  return (
    <header className="border-b border-emerald-700 bg-slate-900/95">
      <div className="mx-auto max-w-[1920px] px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">
          Preparación ofensiva
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-100">PocketIQ</h1>
        <p className="mt-1 text-lg font-semibold text-emerald-300">
          ¿Cómo nos va a atacar esta defensa?
        </p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
          Herramienta de preparación ofensiva basada en tendencias históricas de presión, protección y tracking.
        </p>
      </div>
    </header>
  )
}
