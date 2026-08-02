import { useEffect, useState } from "react";
import { getAttendance, exportCsvUrl, exportXlsxUrl } from "../api";
import { Search, Download, Printer, RotateCcw } from "lucide-react";

function AttendanceLog() {
  const [records, setRecords] = useState([]);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [startDate, setStartDate] = useState(new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));

  const load = () => {
    getAttendance({
      start_date: startDate, end_date: endDate,
      search: search || undefined, department: department || undefined, status: status || undefined,
    }).then(setRecords);
  };

  const clearFilters = () => {
    setSearch("");
    setDepartment("");
    setStatus("");
    setStartDate("");
    setEndDate("");
    getAttendance({}).then(setRecords);
  };
  
  useEffect(() => { load(); }, []);

  const departments = [...new Set(records.map((r) => r.department).filter(Boolean))];
  const statuses = [...new Set(records.map((r) => r.status).filter(Boolean))];

  return (
    <div>
      {/* Top Section: Filters (Left) and Actions (Right) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
        
        {/* Filters Group */}
        <div>
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

          <div className="filter-row">
            <div className="search-field">
              <Search size={15} />
              <input placeholder="Search by employee name" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <select value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">All departments</option>
              {departments.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* Actions Group (Aligned Right) */}
        <div className="action-row" style={{ margin: 0 }}>
          <a className="btn-secondary" href={exportCsvUrl()}>
            <Download size={16} /> Download CSV
          </a>
          <a className="btn-secondary" href={exportXlsxUrl()}>
            <Download size={16} /> Download XLSX
          </a>
          <button className="btn-secondary" onClick={() => window.print()}>
            <Printer size={16} /> Print
          </button>
        </div>
      </div>

      {/* Data Table */}
      <table className="data-table">
        <thead>
          <tr>
            <th>Employee ID</th><th>Employee Name</th><th>Department</th><th>Date</th>
            <th>Entry Camera</th><th>Entry Time</th><th>Exit Camera</th><th>Exit Time</th>
            <th>Status</th><th>Wore Mask</th><th>Work Hours</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={i}>
              <td>{r.employee_id}</td><td>{r.name}</td><td>{r.department}</td><td>{r.date}</td>
              <td>main gate in</td><td>{r.check_in || "—"}</td>
              <td>main gate out</td><td>{r.check_out || "—"}</td>
              <td>{r.status}</td><td>{r.wore_mask}</td><td>{r.work_hours ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      
      {records.length === 0 && <p style={{ marginTop: "16px", color: "var(--text-muted)" }}>No attendance records for this filter.</p>}
    </div>
  );
}

export default AttendanceLog;