import { useState, type FormEvent } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Field } from "../components/ui";
import { api, toError, type Role } from "../lib/api";
import { homeFor, useAuth } from "../lib/auth";

interface Form { email: string; password: string }

// Real deployments must not advertise a login. VITE_DEMO opens the read-only account, for a public demo.
const DEMO_ENABLED = import.meta.env.DEV || import.meta.env.VITE_DEMO === "1";
const DEMO_ACCOUNTS = import.meta.env.DEV ? ["admin", "analyst", "reviewer", "viewer"] : ["viewer"];
const DEMO_PASSWORD = "afed1234";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [error, setError] = useState("");
  const [forgot, setForgot] = useState(false);
  const [notice, setNotice] = useState("");
  const prefill = DEMO_ENABLED && params.has("demo");
  const { register, handleSubmit, setValue, getValues, formState: { errors, isSubmitting } } = useForm<Form>({
    defaultValues: prefill ? { email: "viewer@afed.app", password: DEMO_PASSWORD } : { email: "", password: "" },
  });

  // Back to the page that asked for a login. Same-site paths only.
  const wanted = (location.state as { from?: string } | null)?.from ?? params.get("next");
  // One leading slash and no backslash anywhere: browsers read "/\host" as "//host", another site.
  const destination = (role: Role) => (wanted && /^\/(?![/\\])[^\\]*$/.test(wanted) ? wanted : homeFor(role));

  if (user) return <Navigate to={destination(user.role)} replace />;

  const signIn = handleSubmit(async ({ email, password }) => {
    setError("");
    try {
      navigate(destination((await login(email, password)).role), { replace: true });
    } catch (e) {
      setError(toError(e).message);
    }
  });

  const requestReset = async (event: FormEvent) => {
    event.preventDefault();
    const email = getValues("email");
    if (!email) { setError("Enter your email first."); return; }
    setError("");
    try {
      setNotice((await api.post<{ message: string }>("/auth/forgot", { email })).data.message);
    } catch (e) {
      setError(toError(e).message);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="on-olive hidden items-center justify-center bg-olive-900 p-12 text-cream-100 lg:flex">
        <div>
          <Link to="/" className="font-serif font-black leading-[0.85] tracking-tight" style={{ fontSize: "clamp(6rem, 13vw, 13rem)" }}>AFED</Link>
          <p className="mt-8 max-w-md font-serif text-3xl italic leading-snug">Every invoice, compared with the vendor's own history.</p>
        </div>
      </div>
      <div className="flex items-center justify-center bg-surface p-6">
        <form onSubmit={forgot ? requestReset : signIn} className="w-full max-w-sm space-y-4" noValidate>
          <h1 className="font-serif text-3xl">{forgot ? "Reset your password" : "Sign in"}</h1>
          <Field label="Email" error={errors.email?.message}>
            <input className="input" type="email" autoComplete="email" {...register("email", { required: "Enter your email" })} />
          </Field>
          {!forgot && (
            <Field label="Password" error={errors.password?.message}>
              <input className="input" type="password" autoComplete="current-password" {...register("password", { required: "Enter your password" })} />
            </Field>
          )}
          {error && <p role="alert" className="notice-error">{error}</p>}
          {notice && <p role="status" className="text-sm text-muted">{notice}</p>}
          <Button type="submit" className="w-full" disabled={isSubmitting}>{forgot ? "Request a reset" : isSubmitting ? "Signing in..." : "Sign in"}</Button>
          <button type="button" className="text-sm text-muted underline underline-offset-2" onClick={() => { setForgot(!forgot); setNotice(""); setError(""); }}>
            {forgot ? "Back to sign in" : "Forgot password?"}
          </button>
          {DEMO_ENABLED && (
            <div className="border-t border-line pt-4 text-sm">
              <p className="mb-2 text-xs text-muted">Demo accounts, password {DEMO_PASSWORD}</p>
              <div className="flex flex-wrap gap-2">
                {DEMO_ACCOUNTS.map((name) => (
                  <button key={name} type="button" className="rounded border border-line px-2 py-1 text-xs capitalize hover:bg-bg"
                    onClick={() => { setValue("email", `${name}@afed.app`); setValue("password", DEMO_PASSWORD); }}>
                    {name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
