import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import {
  ScanFace,
  LayoutDashboard,
  Camera,
  Users,
  UserPlus,
  Contact,
  ClipboardList,
  Settings as SettingsIcon,
} from "lucide-react";

const CAMERA_NAMES = ["main gate in", "main gate out"];

function Layout() {
  const [cameraToggles, setCameraToggles] = useState(
    Object.fromEntries(CAMERA_NAMES.map((n) => [n, n === "main gate in"]))
  );

  const toggleCamera = (name) => {
    setCameraToggles((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const navItems = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/checkin", label: "Check In / Out", icon: Camera },
    { to: "/employees", label: "Employees", icon: Users },
    { to: "/add-employee", label: "Add Employee", icon: UserPlus },
    { to: "/visitors", label: "Visitors", icon: Contact },
    { to: "/attendance", label: "Attendance Log", icon: ClipboardList },
    { to: "/settings", label: "Settings", icon: SettingsIcon },
  ];

  // 1. Initialize useLocation
  const location = useLocation();

  // 2. Map current path to page title based on your navItems
  const getPageTitle = (pathname) => {
    switch (pathname) {
      case '/': return 'Dashboard';
      case '/checkin': return 'Check In / Out';
      case '/employees': return 'Employees';
      case '/add-employee': return 'Add Employee';
      case '/visitors': return 'Visitors';
      case '/attendance': return 'Attendance Log';
      case '/settings': return 'Settings';
      default: return 'Attendance System'; 
    }
  };

  // 3. Store the result
  const pageTitle = getPageTitle(location.pathname);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <ScanFace size={19} strokeWidth={2} />
          </div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">Control Panel</span>
            <span className="sidebar-brand-subtitle">Attendance system</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => "nav-link" + (isActive ? " nav-link-active" : "")}
              >
                <Icon size={17} strokeWidth={2} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-footer"> Attendance</div>
      </aside>

      <div className="main-area">
        <div className="cam-bar">
          <span className="cam-bar-label">Cameras</span>
          {CAMERA_NAMES.map((name) => (
            <label key={name} className="cam-toggle">
              <input
                type="checkbox"
                checked={cameraToggles[name]}
                onChange={() => toggleCamera(name)}
              />
              <span>{name}</span>
            </label>
          ))}
        </div>

        <header className="app-header">
          {/* 4. Use the dynamic pageTitle variable here */}
          <h1 className="app-title">{pageTitle}</h1>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default Layout;