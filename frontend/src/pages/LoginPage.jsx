import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Leaf } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ErrorAlert } from "../components/Ui";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(form);
      navigate(location.state?.from?.pathname || "/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-panel hero-panel">
        <div className="hero-icon"><Leaf /></div>
        <h1>Welcome back to KrishiMitra</h1>
        <p>AI-powered farming support for schemes, crop disease detection, grievances, chat, and voice assistance.</p>
      </section>
      <section className="auth-panel form-panel">
        <h2>Sign in</h2>
        <p className="muted">Use your registered farmer, officer, or admin account.</p>
        <ErrorAlert error={error} />
        <form onSubmit={handleSubmit} className="form-stack">
          <label>Email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label>Password<input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <button className="primary-button" disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="muted">New here? <Link to="/register">Create an account</Link></p>
      </section>
    </div>
  );
}
