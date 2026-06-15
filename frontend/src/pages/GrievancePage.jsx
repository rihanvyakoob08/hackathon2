import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorAlert, SuccessAlert } from "../components/Ui";

const categories = ["Subsidy Delay", "Crop Loss", "Insurance", "Irrigation", "Market Rate Issue"];

export default function GrievancePage() {
  const [form, setForm] = useState({ category: categories[0], title: "", description: "", district: "" });
  const [trackingId, setTrackingId] = useState("");
  const [tracked, setTracked] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api.myGrievances().then(setItems).catch(() => null);
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    try {
      const response = await api.createGrievance(form);
      setItems((current) => [response, ...current]);
      setSuccess(`Grievance submitted. Tracking ID: ${response.tracking_id}`);
      setForm({ category: categories[0], title: "", description: "", district: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function track(event) {
    event.preventDefault();
    setError("");
    setTracked(null);
    try {
      const response = await api.trackGrievance(trackingId);
      setTracked(response);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header className="page-header"><h2>Grievances</h2><p>Submit a complaint and track resolution progress using the tracking ID.</p></header>
      <ErrorAlert error={error} />
      <SuccessAlert message={success} />
      <div className="two-column">
        <section className="panel">
          <h3>Create grievance</h3>
          <form className="form-stack" onSubmit={submit}>
            <label>Category<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
            <label>District<input value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} /></label>
            <label>Description<textarea required rows="5" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
            <button className="primary-button">Submit grievance</button>
          </form>
        </section>
        <section className="panel">
          <h3>Track grievance</h3>
          <form className="inline-form" onSubmit={track}>
            <input value={trackingId} onChange={(e) => setTrackingId(e.target.value)} placeholder="GRV2026xxxxx" required />
            <button className="primary-button">Track</button>
          </form>
          {tracked && <div className="tracking-card"><strong>{tracked.tracking_id}</strong><span>{tracked.status}</span><h4>{tracked.title}</h4><p>{tracked.description}</p><p><b>Officer:</b> {tracked.assigned_officer || "Not assigned"}</p><p><b>Notes:</b> {tracked.resolution_notes || "No notes yet"}</p></div>}
        </section>
      </div>
      <section className="panel">
        <h3>My grievances</h3>
        {items.length === 0 ? <EmptyState title="No grievances" message="Submitted grievances will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Tracking</th><th>Title</th><th>Category</th><th>Status</th><th>District</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.tracking_id}</td><td>{item.title}</td><td>{item.category}</td><td><span className="pill">{item.status}</span></td><td>{item.district}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}
