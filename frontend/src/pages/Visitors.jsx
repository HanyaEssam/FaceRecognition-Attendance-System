import { useEffect, useState } from "react";
import { getVisitors } from "../api";

function Visitors() {
  const [data, setData] = useState(null);

  useEffect(() => { getVisitors().then(setData); }, []);

  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <p className="hint">
        Anyone detected during Check In / Out who does not match an enrolled employee
        is logged here as a guest, instead of blocking them with an error. Their session
        stays open until they check out, at which point a duration is calculated.
      </p>

      <div className="stat-grid">
        <div className="stat-card tone-info">
          <div className="stat-label">VISITORS THIS MONTH</div>
          <div className="stat-value">{data.count_this_month}</div>
        </div>
        <div className="stat-card tone-accent">
          <div className="stat-label">TOTAL VISITORS (ALL-TIME)</div>
          <div className="stat-value">{data.total_all_time}</div>
        </div>
      </div>

      <table className="data-table" style={{ marginTop: 16 }}>
        <thead>
          <tr>
            <th>Date</th><th>Check In</th><th>Check Out</th>
            <th>Entry Camera</th><th>Exit Camera</th>
            <th>Duration (min)</th><th>Similarity to Employees</th>
          </tr>
        </thead>
        <tbody>
          {data.records.map((v, i) => (
            <tr key={i}>
              <td>{v.date}</td>
              <td>{v.check_in || "—"}</td>
              <td>{v.check_out || <span className="hint">still on-site</span>}</td>
              <td>{v.camera_in || "—"}</td>
              <td>{v.camera_out || "—"}</td>
              <td>{v.duration_minutes != null ? v.duration_minutes : "—"}</td>
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