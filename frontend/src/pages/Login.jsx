import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { homeFor } from "../auth/permissions";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await login(form.email, form.password);
      navigate(location.state?.from || homeFor(me.role), { replace: true });
    } catch (err) {
      setError(err.status === 401 || err.status === 400 ? "Email or password is incorrect." : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <form onSubmit={submit} className="panel w-full max-w-sm p-6" noValidate>
        <h1 className="font-serif text-2xl font-semibold">Sign in to Gradebook</h1>
        <p className="mt-1 text-sm text-ink-500">Assignments, grading and appeals in one place.</p>
        {error && (
          <p role="alert" className="mt-4 rounded-md bg-mark-50 p-3 text-sm text-mark-700">
            {error}
          </p>
        )}
        <div className="mt-5">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="username" required className="input" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div className="mt-4">
          <label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" required className="input" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <button className="btn-primary mt-6 w-full" disabled={busy || !form.email || !form.password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
