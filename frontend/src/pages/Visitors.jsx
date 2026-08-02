import { useEffect, useState } from "react";
import { getVisitors } from "../api";
import { Contact, Info } from "lucide-react";

function Visitors() {
  const [data, setData] = useState(null);

  useEffect(() => { getVisitors().then(setData); }, []);

  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <p className="hint">
        <Info size={15} />
        Anyone detected during Check In / Out who does not match an enrolled employee
        is logged here as a guest, instead of blocking them with an error.
      </p>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-card-text">
            <span className="stat-label">Visitors this month</span>
            <span className="stat-value">{data.count_this_month}</span>
          </div>
          <div className="stat-icon" style={{ background: "var(--teal-soft)", color: "var(--teal)" }}>
            <Contact size={19} strokeWidth={2} />
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-text">
            <span className="stat-label">Total visitors (all-time)</span>
            <span className="stat-value">{data.total_all_time}</span>
          </div>
          <div className="stat-icon" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
            <Contact size={19} strokeWidth={2} />
          </div>
        </div>
      </div>

      <table className="data-table" style={{ marginTop: 16 }}>
        <thead><tr><th>Date</th><th>Time</th><th>Camera</th><th>Best Similarity</th></tr></thead>
        <tbody>
          {data.records.map((v, i) => (
            <tr key={i}>
              <td>{v.date}</td><td>{v.time}</td><td>{v.camera}</td>
              <td>{v.best_similarity != null ? v.best_similarity.toFixed(2) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.records.length === 0 && <p>No visitors logged yet.</p>}
    </div>
  );
}

export default Visitors;
