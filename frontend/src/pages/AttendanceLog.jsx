import { useEffect, useState } from "react";
import { getAttendance, getAttendanceSummary, exportCsvUrl, exportXlsxUrl } from "../api";
import { Search, Download, Printer, RotateCcw } from "lucide-react";

function AttendanceLog() {
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState([]);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [startDate, setStartDate] = useState(new Date(Date.now()).toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));

  const load = () => {
    getAttendance({
      start_date: startDate, end_date: endDate,
      search: search || undefined, department: department || undefined, status: status || undefined,
    }).then(setRecords);

    getAttendanceSummary({
      start_date: startDate, end_date: endDate,
      search: search || undefined, department: department || undefined,
    }).then(setSummary);
  };

  const clearFilters = () => {
    setSearch("");
    setDepartment("");
    setStatus("");
    setStartDate("");
    setEndDate("");
    getAttendance({}).then(setRecords);
    getAttendanceSummary({}).then(setSummary);
  };

  useEffect(() => { load(); }, []);

  const departments = [...new Set(records.map((r) => r.department).filter(Boolean))];
  const statuses = [...new Set(records.map((r) => r.status).filter(Boolean))];

  return (
    <div>
      {/* Top Section: Filters (Left) and Actions (Right) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>

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

      {/* Daily Hours Summary Table */}
      <h3 style={{ marginBottom: 8 }}>Daily Hours Summary</h3>
      <table className="data-table" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Employee ID</th><th>Employee Name</th><th>Department</th>
            <th>Date</th><th>Total Working Hours</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((s, i) => (
            <tr key={i}>
              <td>{s.employee_id}</td><td>{s.name}</td><td>{s.department}</td>
              <td>{s.date}</td><td>{s.total_work_hours ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {summary.length === 0 && <p style={{ marginBottom: 24, color: "var(--text-muted)" }}>No summary data for this filter.</p>}

      {/* All Sessions / Logs Table */}
      <h3 style={{ marginBottom: 8 }}>All Check-In / Check-Out Logs</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Employee ID</th><th>Employee Name</th><th>Department</th><th>Date</th>
            <th>Entry Camera</th><th>Entry Time</th><th>Exit Camera</th><th>Exit Time</th>
            <th>Status</th><th>Work Hours</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={i}>
              <td>{r.employee_id}</td><td>{r.name}</td><td>{r.department}</td><td>{r.date}</td>
              <td>main gate in</td><td>{r.check_in || "—"}</td>
              <td>main gate out</td><td>{r.check_out || "—"}</td>
              <td>{r.status}</td><td>{r.work_hours ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {records.length === 0 && <p style={{ marginTop: "16px", color: "var(--text-muted)" }}>No attendance records for this filter.</p>}
    </div>
  );
}

export default AttendanceLog;