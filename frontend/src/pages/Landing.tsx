import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Landing() {
  const { user } = useAuth();
  useEffect(() => { document.title = "AFED · Automated Fraud and Event Detection"; }, []);
  return (
    <main className="on-olive flex h-screen flex-col items-center justify-center overflow-hidden bg-olive-900 px-6 text-center text-cream-100">
      <h1 className="fade-up font-serif font-black leading-[0.85] tracking-tight" style={{ fontSize: "clamp(7rem, 21vw, 21rem)" }}>AFED</h1>
      <p className="fade-up mt-6 text-sm uppercase tracking-[0.35em] text-cream-300 sm:text-base" style={{ animationDelay: "120ms" }}>
        Automated Fraud and Event Detection
      </p>
      <Link to={user ? "/dashboard" : "/login"} style={{ animationDelay: "240ms" }}
        className="fade-up group mt-12 inline-flex items-center gap-3 rounded-full bg-clay-600 px-8 py-3.5 text-base font-semibold text-cream-100 shadow-lg shadow-black/20 transition hover:bg-clay-700">
        Open dashboard <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">→</span>
      </Link>
    </main>
  );
}
