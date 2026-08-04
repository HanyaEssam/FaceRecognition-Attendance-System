import { useEffect, useState } from "react";
import { getVisitors, getVisitorPhotoUrl } from "../api";

function Visitors() {
  const [data, setData] = useState(null);
  const [loadingPhotoId, setLoadingPhotoId] = useState(null);

  useEffect(() => { getVisitors().then(setData); }, []);

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