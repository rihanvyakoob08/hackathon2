import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorAlert, SuccessAlert } from "../components/Ui";
import { useAuth } from "../context/AuthContext";

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const [userForm, setUserForm] = useState({ full_name: user?.full_name || "", phone: user?.phone || "", preferred_language: user?.preferred_language || "ta" });
  const [profile, setProfile] = useState({ state: "", district: "", village: "", land_size_acres: "", primary_crop: "", irrigation_type: "", farmer_category: "", annual_income: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api.getProfile().then((data) => setProfile((current) => ({ ...current, ...data }))).catch(() => null);
  }, []);

  async function saveUser(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    try {
      const updated = await api.updateMe(userForm);
      setUser(updated);
      setSuccess("Account updated.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    try {
      const payload = { ...profile, land_size_acres: Number(profile.land_size_acres) || null, annual_income: Number(profile.annual_income) || null };
      const updated = await api.updateProfile(payload);
      setProfile(updated);
      setSuccess("Farmer profile saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header className="page-header"><h2>Profile</h2><p>Update account and farming details used by AI recommendations.</p></header>
      <ErrorAlert error={error} />
      <SuccessAlert message={success} />
      <div className="two-column">
        <section className="panel">
          <h3>Account</h3>
          <form className="form-stack" onSubmit={saveUser}>
            <label>Full name<input value={userForm.full_name} onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })} /></label>
            <label>Phone<input value={userForm.phone || ""} onChange={(e) => setUserForm({ ...userForm, phone: e.target.value })} /></label>
            <label>Language<select value={userForm.preferred_language} onChange={(e) => setUserForm({ ...userForm, preferred_language: e.target.value })}><option value="ta">Tamil</option><option value="hi">Hindi</option><option value="kn">Kannada</option><option value="en">English</option></select></label>
            <button className="primary-button">Save account</button>
          </form>
        </section>
        <section className="panel">
          <h3>Farmer details</h3>
          <form className="form-grid" onSubmit={saveProfile}>
            {[["state", "State"], ["district", "District"], ["village", "Village"], ["primary_crop", "Primary crop"], ["land_size_acres", "Land acres"], ["irrigation_type", "Irrigation"], ["farmer_category", "Farmer category"], ["annual_income", "Annual income"]].map(([key, label]) => (
              <label key={key}>{label}<input value={profile[key] || ""} onChange={(e) => setProfile({ ...profile, [key]: e.target.value })} /></label>
            ))}
            <button className="primary-button full-row">Save farmer profile</button>
          </form>
        </section>
      </div>
    </div>
  );
}

