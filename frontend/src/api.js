import axios from "axios";

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000/api"
).replace(/\/+$/, "");

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const getEmployees = () =>
  api.get("/employees").then((response) => response.data);

export const createEmployee = (payload) =>
  api.post("/employees", payload).then((response) => response.data);

export const updateEmployee = (id, payload) =>
  api.put(`/employees/${id}`, payload).then((response) => response.data);

export const deleteEmployee = (id) =>
  api.delete(`/employees/${id}`).then((response) => response.data);

export const checkIn = (payload) =>
  api.post("/checkin", payload).then((response) => response.data);

export const getAttendance = (params = {}) =>
  api.get("/attendance", { params }).then((response) => response.data);

export const exportCsvUrl = () =>
  `${API_BASE_URL}/attendance/export/csv`;

export const exportXlsxUrl = () =>
  `${API_BASE_URL}/attendance/export/xlsx`;

export const getVisitors = () =>
  api.get("/visitors").then((response) => response.data);

export const getDashboardStats = () =>
  api.get("/dashboard/stats").then((response) => response.data);

export const getHealth = () =>
  api.get("/health").then((response) => response.data);

export default api;