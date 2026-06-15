import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { ErrorAlert } from "../components/Ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    role: "farmer",
    preferred_language: "ta",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page compact">
      <section className="auth-panel form-panel wide">
        <h2>Create account</h2>
        <p className="muted">Register as a farmer, officer, or admin for demo access.</p>
        <ErrorAlert error={error} />
        <form onSubmit={handleSubmit} className="form-grid">
          <label>Full name<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
          <label>Email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label>Phone<input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
          <label>Password<input type="password" minLength="6" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <label>Role<select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="farmer">Farmer</option><option value="officer">Officer</option><option value="admin">Admin</option></select></label>
          <label>Language<select value={form.preferred_language} onChange={(e) => setForm({ ...form, preferred_language: e.target.value })}><option value="ta">Tamil</option><option value="hi">Hindi</option><option value="kn">Kannada</option><option value="en">English</option></select></label>
          <button className="primary-button full-row" disabled={loading}>{loading ? "Creating..." : "Create account"}</button>
        </form>
        <p className="muted">Already registered? <Link to="/login">Sign in</Link></p>
      </section>
    </div>
  );
}

