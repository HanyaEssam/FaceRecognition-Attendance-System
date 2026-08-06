import { useEffect, useState } from "react";
import { Download, RotateCcw, Search } from "lucide-react";
import {
  exportVisitorsCsvUrl,
  exportVisitorsXlsxUrl,
  getVisitors,
  getVisitorPhotoUrl,
} from "../api";

function Visitors() {
  const [data, setData] = useState(null);
  const [loadingPhotoId, setLoadingPhotoId] = useState(null);
  const [startDate, setStartDate] = useState(
    new Date(Date.now()).toISOString().slice(0, 10)
  );
  const [endDate, setEndDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const load = () => {
    getVisitors({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    }).then(setData);
  };

  const clearFilters = () => {
    setStartDate("");
    setEndDate("");
    getVisitors().then(setData);
  };

  useEffect(() => { load(); }, []);

  const handleViewPhoto = async (visitorId) => {
    setLoadingPhotoId(visitorId);
    try {
      const { url } = await getVisitorPhotoUrl(visitorId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      alert(err.response?.data?.detail || "Could not load photo.");
    } finally {
      setLoadingPhotoId(null);
    }
  };

  if (!data) return <p>Loading…</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
        <div className="filter-row">
          <label>Start <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
          <label>End <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
          <button className="btn-primary" onClick={load}>
            <Search size={16} /> Search
          </button>
          <button className="btn-secondary" onClick={clearFilters}>
            <RotateCcw size={16} /> Clear filters
          </button>
        </div>

        <div className="action-row" style={{ margin: 0 }}>
          <a className="btn-secondary" href={exportVisitorsCsvUrl({ start_date: startDate, end_date: endDate })}>
            <Download size={16} /> Download CSV
          </a>
          <a className="btn-secondary" href={exportVisitorsXlsxUrl({ start_date: startDate, end_date: endDate })}>
            <Download size={16} /> Download XLSX
          </a>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card tone-info">
          <div className="stat-label">VISITORS TODAY</div>
          <div className="stat-value">{data.count_today}</div>
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
            <th>Duration (min)</th><th>Similarity to Employees</th><th>Photo</th>
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
              <td>
                {v.photo_path ? (
                  <button
                    className="btn-link"
                    onClick={() => handleViewPhoto(v.id)}
                    disabled={loadingPhotoId === v.id}
                  >
                    {loadingPhotoId === v.id ? "Loading…" : "View"}
                  </button>
                ) : (
                  <span className="hint">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.records.length === 0 && <p>No visitors logged yet.</p>}
    </div>
  );
}

export default Visitors;
