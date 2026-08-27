import { StatusView } from "./views/StatusView";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">NEER — Water Intelligence</h1>
        <p className="text-sm text-slate-500">
          Decision-support dashboard (Phase 0)
        </p>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-8">
        <StatusView />
      </main>
    </div>
  );
}
