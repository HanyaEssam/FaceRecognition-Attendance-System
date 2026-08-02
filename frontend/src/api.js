import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

export const getEmployees = () => api.get("/employees").then(r => r.data);

export const createEmployee = (payload) => api.post("/employees", payload).then(r => r.data);

export const updateEmployee = (id, payload) => api.put(`/employees/${id}`, payload).then(r => r.data);

export const deleteEmployee = (id) => api.delete(`/employees/${id}`).then(r => r.data);

export const checkIn = (payload) => api.post("/checkin", payload).then(r => r.data);

export const getAttendance = (params = {}) => api.get("/attendance", { params }).then(r => r.data);

export const exportCsvUrl = () => "http://localhost:8000/api/attendance/export/csv";
export const exportXlsxUrl = () => "http://localhost:8000/api/attendance/export/xlsx";

export const getVisitors = () => api.get("/visitors").then(r => r.data);

export const getDashboardStats = () => api.get("/dashboard/stats").then(r => r.data);

export const getHealth = () => api.get("/health").then(r => r.data);

export default api;
