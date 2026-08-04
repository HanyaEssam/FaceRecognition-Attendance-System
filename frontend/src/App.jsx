import { BrowserRouter, Routes, Route } from "react-router-dom";

import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import CheckInOut from "./pages/CheckInOut";
import Kiosk from "./pages/Kiosk";
import Employees from "./pages/Employees";
import AddEmployee from "./pages/AddEmployee";
import Visitors from "./pages/Visitors";
import AttendanceLog from "./pages/AttendanceLog";
import Settings from "./pages/Settings";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />

          <Route
            path="checkin"
            element={<CheckInOut />}
          />

          <Route
            path="kiosk"
            element={<Kiosk />}
          />

          <Route
            path="employees"
            element={<Employees />}
          />

          <Route
            path="add-employee"
            element={<AddEmployee />}
          />

          <Route
            path="visitors"
            element={<Visitors />}
          />

          <Route
            path="attendance"
            element={<AttendanceLog />}
          />

          <Route
            path="settings"
            element={<Settings />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;