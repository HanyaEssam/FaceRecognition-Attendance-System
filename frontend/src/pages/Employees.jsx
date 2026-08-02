import { useEffect, useState } from "react";
import { getEmployees, updateEmployee, deleteEmployee } from "../api";
import { Search, Save, Trash2, Info } from "lucide-react";

function Employees() {
  const [employees, setEmployees] = useState([]);
  const [search, setSearch] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [profile, setProfile] = useState({});
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [message, setMessage] = useState(null);

  const load = () => getEmployees().then((data) => {
    setEmployees(data);
    if (data.length && selectedId == null) {
      setSelectedId(data[0].id);
      setProfile(data[0]);
    }
  });

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const emp = employees.find((e) => e.id === selectedId);
    if (emp) setProfile(emp);
  }, [selectedId, employees]);

  const departments = [...new Set(employees.map((e) => e.department).filter(Boolean))];

  const filtered = employees.filter((e) => {
    const matchesSearch = !search || e.name.toLowerCase().includes(search.toLowerCase());
    const matchesDept = !deptFilter || e.department === deptFilter;
    return matchesSearch && matchesDept;
  });

  const saveProfile = async () => {
    await updateEmployee(selectedId, {
      national_id: profile.national_id, job_title: profile.job_title, gender: profile.gender,
      religion: profile.religion, marital_status: profile.marital_status,
      birth_date: profile.birth_date, address: profile.address, employee_status: profile.employee_status,
    });
    setMessage("Profile updated.");
    load();
  };

  const handleDelete = async () => {
    await deleteEmployee(selectedId);
    setMessage(`Deleted ${profile.name}.`);
    setSelectedId(null);
    setConfirmDelete(false);
    load();
  };

  return (
    <div>
      <div className="filter-row">
        <div className="search-field">
          <Search size={15} />
          <input placeholder="Search by employee name" value={search}
                 onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      <table className="data-table">
        <thead>
          <tr><th>ID</th><th>Name</th><th>Department</th><th>Job Title</th><th>Shift Start</th><th>Status</th></tr>
        </thead>
        <tbody>
          {filtered.map((e) => (
            <tr key={e.id} onClick={() => setSelectedId(e.id)}
                className={e.id === selectedId ? "row-selected" : ""}>
              <td>{e.id}</td><td>{e.name}</td><td>{e.department}</td>
              <td>{e.job_title || "—"}</td><td>{e.shift_start}</td><td>{e.employee_status}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {profile.id && (
        <>
          <hr />
          <h3>Employee profile (by Employee ID {profile.id})</h3>
          <p className="hint">
            <Info size={15} />
            In production, these fields would sync automatically from your HR system by
            Employee ID. For now they're stored locally and editable here.
          </p>
          <div className="profile-grid">
            <label>National ID <input value={profile.national_id || ""} onChange={(e) => setProfile({ ...profile, national_id: e.target.value })} /></label>
            <label>Job Title <input value={profile.job_title || ""} onChange={(e) => setProfile({ ...profile, job_title: e.target.value })} /></label>
            <label>Gender
              <select value={profile.gender || ""} onChange={(e) => setProfile({ ...profile, gender: e.target.value })}>
                <option value="">—</option><option value="Male">Male</option><option value="Female">Female</option>
              </select>
            </label>
            <label>Religion <input value={profile.religion || ""} onChange={(e) => setProfile({ ...profile, religion: e.target.value })} /></label>
            <label>Marital Status <input value={profile.marital_status || ""} onChange={(e) => setProfile({ ...profile, marital_status: e.target.value })} /></label>
            <label>Birth Date <input value={profile.birth_date || ""} onChange={(e) => setProfile({ ...profile, birth_date: e.target.value })} placeholder="YYYY-MM-DD" /></label>
            <label>Address <input value={profile.address || ""} onChange={(e) => setProfile({ ...profile, address: e.target.value })} /></label>
            <label>Status
              <select value={profile.employee_status || "whitelist"} onChange={(e) => setProfile({ ...profile, employee_status: e.target.value })}>
                <option value="whitelist">whitelist</option><option value="blacklist">blacklist</option>
              </select>
            </label>
          </div>
          <button className="btn-primary" onClick={saveProfile}>
            <Save size={16} /> Save profile changes
          </button>

          <hr />
          <h3>Delete this employee</h3>
          <p className="hint">
            <Info size={15} />
            This permanently removes the employee AND their attendance history. There's no undo.
          </p>
          <label>
            <input type="checkbox" checked={confirmDelete} onChange={(e) => setConfirmDelete(e.target.checked)} />
            {" "}I understand this permanently deletes {profile.name} and their attendance records.
          </label>
          <br />
          <button className="btn-danger" disabled={!confirmDelete} onClick={handleDelete}>
            <Trash2 size={16} /> Delete employee
          </button>
        </>
      )}

      {message && <div className="alert alert-info" style={{ marginTop: 12 }}>{message}</div>}
    </div>
  );
}

export default Employees;
