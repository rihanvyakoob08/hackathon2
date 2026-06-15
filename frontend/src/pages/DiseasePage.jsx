import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorAlert } from "../components/Ui";

export default function DiseasePage() {
  const [cropType, setCropType] = useState("");
  const [image, setImage] = useState(null);
  const [result, setResult] = useState(null);
  const [reports, setReports] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.diseaseReports().then(setReports).catch(() => null);
  }, []);

  async function analyze(event) {
    event.preventDefault();
    if (!image) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("image", image);
      if (cropType) formData.append("crop_type", cropType);
      const response = await api.analyzeDisease(formData);
      setResult(response);
      setReports((items) => [response, ...items]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header"><h2>Crop Disease Detection</h2><p>Upload a crop image to identify disease, pest, severity, and treatment guidance.</p></header>
      <ErrorAlert error={error} />
      <div className="two-column">
        <section className="panel">
          <h3>Analyze image</h3>
          <form className="form-stack" onSubmit={analyze}>
            <label>Crop type<input value={cropType} onChange={(e) => setCropType(e.target.value)} placeholder="Paddy, cotton, tomato..." /></label>
            <label>Crop image<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setImage(e.target.files?.[0])} required /></label>
            <button className="primary-button" disabled={loading}>{loading ? "Analyzing..." : "Analyze disease"}</button>
          </form>
        </section>
        <section className="panel result-panel">
          <h3>Latest result</h3>
          {!result ? <EmptyState title="No result yet" message="Upload an image to see AI analysis." /> : (
            <div className="result-list">
              <strong>{result.disease_name || result.pest_name || "Observation"}</strong>
              <span>Severity: {result.severity || "Unknown"}</span>
              <span>Confidence: {result.confidence_score ?? "N/A"}</span>
              <p>{result.description}</p>
              <p><b>Treatment:</b> {result.treatment}</p>
            </div>
          )}
        </section>
      </div>
      <section className="panel">
        <h3>Recent reports</h3>
        {reports.length === 0 ? <EmptyState title="No reports" message="Your disease reports will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Crop</th><th>Disease</th><th>Severity</th><th>Date</th></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.crop_type}</td><td>{report.disease_name || report.pest_name}</td><td>{report.severity}</td><td>{report.created_at ? new Date(report.created_at).toLocaleString() : "-"}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}
