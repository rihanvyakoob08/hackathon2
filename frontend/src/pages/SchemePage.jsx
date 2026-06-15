import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorAlert } from "../components/Ui";

export default function SchemePage() {
  const [schemes, setSchemes] = useState([]);
  const [history, setHistory] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ scheme_name: "PM-KISAN", state: "Tamil Nadu", land_ownership: "owned", farmer_category: "small", annual_income: "" });

  useEffect(() => {
    api.schemes().then(setSchemes).catch(() => null);
    api.schemeHistory().then(setHistory).catch(() => null);
  }, []);

  async function check(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await api.checkScheme({ ...form, annual_income: Number(form.annual_income) || null });
      setResult(response);
      setHistory((items) => [response, ...items]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header"><h2>Scheme Eligibility</h2><p>Check eligibility and documents for agricultural government schemes.</p></header>
      <ErrorAlert error={error} />
      <div className="two-column">
        <section className="panel">
          <h3>Eligibility check</h3>
          <form className="form-stack" onSubmit={check}>
            <label>Scheme<select value={form.scheme_name} onChange={(e) => setForm({ ...form, scheme_name: e.target.value })}>{schemes.map((scheme) => <option key={scheme.name} value={scheme.name}>{scheme.name}</option>)}</select></label>
            <label>State<input value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} /></label>
            <label>Land ownership<input value={form.land_ownership} onChange={(e) => setForm({ ...form, land_ownership: e.target.value })} /></label>
            <label>Farmer category<input value={form.farmer_category} onChange={(e) => setForm({ ...form, farmer_category: e.target.value })} /></label>
            <label>Annual income<input type="number" value={form.annual_income} onChange={(e) => setForm({ ...form, annual_income: e.target.value })} /></label>
            <button className="primary-button" disabled={loading}>{loading ? "Checking..." : "Check eligibility"}</button>
          </form>
        </section>
        <section className="panel result-panel">
          <h3>Result</h3>
          {!result ? <EmptyState title="No check yet" message="Submit the form to see eligibility." /> : (
            <div className={`eligibility ${result.is_eligible === true ? "yes" : result.is_eligible === false ? "no" : ""}`}>
              <strong>{result.eligibility_status === "requires_verification" ? "Needs verification" : result.is_eligible ? "Eligible" : "Not eligible"}</strong>
              <p>{result.eligibility_reason}</p>
              {result.benefits && <p><b>Benefits:</b> {result.benefits}</p>}
              {result.required_documents?.length > 0 && <p><b>Documents:</b> {result.required_documents.join(", ")}</p>}
              {result.application_steps && <p><b>Steps:</b> {result.application_steps}</p>}
            </div>
          )}
        </section>
      </div>
      <section className="panel">
        <h3>Eligibility history</h3>
        {history.length === 0 ? <EmptyState title="No history" message="Your checks will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Scheme</th><th>Status</th><th>Reason</th><th>Date</th></tr></thead><tbody>{history.map((item) => <tr key={item.id}><td>{item.scheme_name}</td><td>{item.is_eligible === true ? "Eligible" : item.is_eligible === false ? "Not eligible" : "Needs verification"}</td><td>{item.eligibility_reason}</td><td>{item.created_at ? new Date(item.created_at).toLocaleDateString() : "-"}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}
