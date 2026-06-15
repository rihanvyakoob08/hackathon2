import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Forward, Search, UserCheck } from "lucide-react";
import { api } from "../api/client";
import { EmptyState, ErrorAlert, StatCard, SuccessAlert } from "../components/Ui";

const statusOptions = [
  { value: "submitted", label: "Submitted" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In Progress" },
  { value: "escalated", label: "Escalated" },
  { value: "closed", label: "Closed" },
];

const slaLabels = {
  on_track: "On track",
  due_soon: "Due soon",
  breached: "Breached",
  closed: "Closed",
};

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function OfficerPage() {
  const [dashboard, setDashboard] = useState(null);
  const [grievances, setGrievances] = useState([]);
  const [reports, setReports] = useState([]);
  const [ivrSessions, setIvrSessions] = useState([]);
  const [staff, setStaff] = useState([]);
  const [selected, setSelected] = useState(null);
  const [trackingId, setTrackingId] = useState("");
  const [notes, setNotes] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const visibleGrievances = useMemo(() => {
    if (statusFilter === "all") return grievances;
    return grievances.filter((item) => item.status === statusFilter);
  }, [grievances, statusFilter]);

  async function load() {
    const [dash, grv, disease, officers, ivrCalls] = await Promise.all([
      api.officerDashboard(),
      api.officerGrievances(),
      api.officerDiseaseReports(),
      api.officerStaff(),
      api.ivrSessions(),
    ]);
    setDashboard(dash);
    setGrievances(grv.data || []);
    setReports(disease);
    setStaff(officers || []);
    setIvrSessions(ivrCalls || []);
  }

  async function openGrievance(id) {
    setError("");
    const detail = await api.officerGrievance(id);
    setSelected(detail);
    setAssigneeId(detail.assigned_officer_id ? String(detail.assigned_officer_id) : "");
    setNotes("");
  }

  useEffect(() => {
    let active = true;
    Promise.all([api.officerDashboard(), api.officerGrievances(), api.officerDiseaseReports(), api.officerStaff(), api.ivrSessions()])
      .then(([dash, grv, disease, officers, ivrCalls]) => {
        if (!active) return;
        setDashboard(dash);
        setGrievances(grv.data || []);
        setReports(disease);
        setStaff(officers || []);
        setIvrSessions(ivrCalls || []);
        if (grv.data?.[0]) openGrievance(grv.data[0].id).catch((err) => active && setError(err.message));
      })
      .catch((err) => {
        if (active) setError(err.message);
      });

    return () => {
      active = false;
    };
  }, []);

  async function track(event) {
    event.preventDefault();
    if (!trackingId.trim()) return;
    setError("");
    setSuccess("");
    try {
      const detail = await api.officerTrackGrievance(trackingId.trim());
      setSelected(detail);
      setAssigneeId(detail.assigned_officer_id ? String(detail.assigned_officer_id) : "");
      setNotes("");
      setSuccess(`Loaded ${detail.tracking_id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateCase(status, defaultNotes) {
    if (!selected) return;
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        status,
        notes: notes.trim() || defaultNotes,
        assigned_officer_id: assigneeId ? Number(assigneeId) : null,
      };
      await api.updateGrievance(selected.id, payload);
      await load();
      await openGrievance(selected.id);
      setSuccess(`Case ${selected.tracking_id} updated.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page officer-workbench">
      <header className="page-header dashboard-header">
        <div>
          <span className="eyebrow">Officer Desk</span>
          <h2>Grievance Workbench</h2>
          <p>Read farmer cases, track SLA, assign ownership, escalate to the next level, and close with resolution notes.</p>
        </div>
      </header>

      <ErrorAlert error={error} />
      <SuccessAlert message={success} />

      <section className="stats-grid">
        <StatCard label="Open grievances" value={dashboard?.pending_grievances} tone="orange" />
        <StatCard label="SLA resolution" value={`${dashboard?.resolution_rate ?? 0}%`} tone="blue" />
        <StatCard label="Disease reports" value={dashboard?.total_disease_reports} tone="red" />
        <StatCard label="IVR calls" value={dashboard?.total_ivr_sessions} />
      </section>

      <section className="officer-grid">
        <div className="panel case-list-panel">
          <div className="case-list-header">
            <h3>Cases</h3>
            <form className="case-track-form" onSubmit={track}>
              <input value={trackingId} onChange={(event) => setTrackingId(event.target.value)} placeholder="Track ID" />
              <button className="icon-button" type="submit" aria-label="Track grievance"><Search size={17} /></button>
            </form>
          </div>
          <div className="status-filter">
            <button className={statusFilter === "all" ? "active" : ""} type="button" onClick={() => setStatusFilter("all")}>All</button>
            {statusOptions.map((item) => (
              <button className={statusFilter === item.value ? "active" : ""} type="button" onClick={() => setStatusFilter(item.value)} key={item.value}>{item.label}</button>
            ))}
          </div>
          {visibleGrievances.length === 0 ? (
            <EmptyState title="No matching grievances" message="Cases appear here when farmers submit grievances." />
          ) : (
            <div className="case-list">
              {visibleGrievances.map((item) => (
                <button className={selected?.id === item.id ? "case-card active" : "case-card"} type="button" onClick={() => openGrievance(item.id)} key={item.id}>
                  <div>
                    <strong>{item.tracking_id}</strong>
                    <span>{item.farmer_name || "Farmer"} · {item.district || "No district"}</span>
                  </div>
                  <p>{item.title}</p>
                  <div className="case-meta">
                    <span className={`sla-pill ${item.sla_status}`}>{slaLabels[item.sla_status] || item.sla_status}</span>
                    <span>{item.days_remaining} days</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="panel case-detail-panel">
          {!selected ? (
            <EmptyState title="Select a grievance" message="Open a case to read details and take action." />
          ) : (
            <>
              <div className="case-title-row">
                <div>
                  <span className="eyebrow">{selected.tracking_id}</span>
                  <h3>{selected.title}</h3>
                </div>
                <span className={`sla-pill ${selected.sla_status}`}>{slaLabels[selected.sla_status] || selected.sla_status}</span>
              </div>

              <dl className="case-facts">
                <div><dt>Status</dt><dd>{selected.status}</dd></div>
                <div><dt>Category</dt><dd>{selected.category}</dd></div>
                <div><dt>Farmer</dt><dd>{selected.farmer_name || "-"}{selected.farmer_phone ? ` · ${selected.farmer_phone}` : ""}</dd></div>
                <div><dt>Assigned</dt><dd>{selected.assigned_officer || "Unassigned"}</dd></div>
                <div><dt>Created</dt><dd>{formatDate(selected.created_at)}</dd></div>
                <div><dt>Due</dt><dd>{formatDate(selected.due_at)}</dd></div>
              </dl>

              <div className="case-description">
                <strong>Grievance</strong>
                <p>{selected.description}</p>
              </div>

              <div className="case-actions">
                <label>Assign owner
                  <select value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}>
                    <option value="">Current officer</option>
                    {staff.map((officer) => (
                      <option value={officer.id} key={officer.id}>{officer.name}{officer.designation ? `, ${officer.designation}` : ""}</option>
                    ))}
                  </select>
                </label>
                <label>Officer notes
                  <textarea rows="4" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Resolution, escalation reason, or next action" />
                </label>
                <div className="action-row">
                  <button className="secondary-button" disabled={loading} onClick={() => updateCase("assigned", "Assigned for review")} type="button"><UserCheck size={16} /> Assign</button>
                  <button className="secondary-button" disabled={loading} onClick={() => updateCase("in_progress", "Case moved to in-progress review")} type="button"><ClipboardCheck size={16} /> Start</button>
                  <button className="secondary-button" disabled={loading} onClick={() => updateCase("escalated", "Escalated to next level for action")} type="button"><Forward size={16} /> Escalate</button>
                  <button className="primary-button" disabled={loading} onClick={() => updateCase("closed", "Closed after officer resolution")} type="button"><CheckCircle2 size={16} /> Close</button>
                </div>
              </div>

              <div className="case-timeline">
                <h3>Audit Trail</h3>
                {selected.updates?.length ? selected.updates.map((update) => (
                  <article key={update.id}>
                    <AlertTriangle size={15} />
                    <div>
                      <strong>{update.status}</strong>
                      <p>{update.notes || "No notes"}</p>
                      <span>{update.updated_by || "System"} · {formatDate(update.created_at)}</span>
                    </div>
                  </article>
                )) : <p className="muted">No officer updates yet.</p>}
              </div>
            </>
          )}
        </div>
      </section>

      <section className="panel">
        <h3>Recent IVR Calls</h3>
        {ivrSessions.length === 0 ? <EmptyState title="No IVR calls" message="Feature-phone IVR sessions will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Phone</th><th>Language</th><th>State</th><th>Intent</th><th>Last transcript</th></tr></thead><tbody>{ivrSessions.slice(0, 8).map((session) => <tr key={session.session_id}><td>{session.phone_number}</td><td>{session.language || "-"}</td><td>{session.current_state}</td><td>{session.last_intent || "-"}</td><td>{session.last_transcript || "-"}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="panel">
        <h3>Recent Disease Reports</h3>
        {reports.length === 0 ? <EmptyState title="No disease reports" message="Recent reports will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Crop</th><th>Disease</th><th>Severity</th><th>District</th><th>Farmer</th></tr></thead><tbody>{reports.slice(0, 8).map((report) => <tr key={report.id}><td>{report.crop_type}</td><td>{report.disease_name}</td><td>{report.severity}</td><td>{report.district}</td><td>{report.farmer}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}
