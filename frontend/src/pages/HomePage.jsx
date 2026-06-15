import { Link, Navigate } from "react-router-dom";
import { Bot, ClipboardList, Landmark, Leaf, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const quickPrompts = [
  { text: "My crop leaves have spots. What should I do?", icon: Leaf },
  { text: "Am I eligible for PM-KISAN?", icon: Landmark },
  { text: "How do I raise a subsidy grievance?", icon: ClipboardList },
];

export default function HomePage() {
  const { user } = useAuth();

  if (user?.role === "officer") {
    return <Navigate to="/officer" replace />;
  }

  if (user?.role === "admin") {
    return <Navigate to="/admin" replace />;
  }

  return (
    <div className="page">
      <header className="page-header dashboard-header">
        <div>
          <span className="eyebrow">Namaste, {user?.full_name}</span>
          <h2>Farmer Dashboard</h2>
          <p>Ask one assistant about crop disease, schemes, weather, and grievances.</p>
        </div>
      </header>

      <section className="dashboard-actions">
        <Link className="primary-action" to="/assistant">
          <Bot size={22} />
          <div>
            <strong>Open AI Assistant</strong>
            <span>One chat for diagnosis, schemes, grievance help, and crop advice.</span>
          </div>
        </Link>
        <Link className="secondary-action" to="/profile">
          <UserRound size={20} />
          <div>
            <strong>Farmer Profile</strong>
            <span>Update crop, district, land, and language details.</span>
          </div>
        </Link>
      </section>

      <section className="panel quick-panel">
        <h3>Common Queries</h3>
        <div className="quick-query-grid">
          {quickPrompts.map(({ text, icon: Icon }) => (
            <Link className="quick-query" to="/assistant" state={{ prompt: text }} key={text}>
              <Icon size={18} />
              <span>{text}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
