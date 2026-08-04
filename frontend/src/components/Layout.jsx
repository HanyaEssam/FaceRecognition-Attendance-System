import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";

import {
  LayoutDashboard,
  Camera,
  Users,
  UserPlus,
  ContactRound,
  ClipboardList,
  Settings,
} from "lucide-react";

const CAMERAS = [
  {
    name: "main gate in",
    direction: "in",
  },
  {
    name: "main gate out",
    direction: "out",
  },
];

function Layout() {
  const [selectedCamera, setSelectedCamera] = useState(CAMERAS[0]);

  const navItems = [
    {
      to: "/",
      label: "Dashboard",
      icon: LayoutDashboard,
      end: true,
    },
    {
      to: "/checkin",
      label: "Check In / Out",
      icon: Camera,
    },
    {
      to: "/kiosk",
      label: "Kiosk Mode",
      icon: Camera,
    },
    {
      to: "/employees",
      label: "Employees",
      icon: Users,
    },
    {
      to: "/add-employee",
      label: "Add Employee",
      icon: UserPlus,
    },
    {
      to: "/visitors",
      label: "Visitors",
      icon: ContactRound,
    },
    {
      to: "/attendance",
      label: "Attendance Log",
      icon: ClipboardList,
    },
    {
      to: "/settings",
      label: "Settings",
      icon: Settings,
    },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">
            <Camera size={24} />
          </div>

          <div>
            <h2 className="sidebar-title">
              Control Panel
            </h2>

            <p className="sidebar-subtitle">
              Attendance system
            </p>
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
                className={({ isActive }) =>
                  `nav-link${
                    isActive
                      ? " nav-link-active"
                      : ""
                  }`
                }
              >
                <Icon size={20} />

                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>

      <div className="main-area">
        <div className="cam-bar">
          <span className="cam-bar-label">
            CAMERAS
          </span>

          {CAMERAS.map((camera) => (
            <label
              key={camera.name}
              className={
                selectedCamera.name === camera.name
                  ? "cam-toggle cam-toggle-active"
                  : "cam-toggle"
              }
            >
              <input
                type="radio"
                name="selected-camera"
                checked={
                  selectedCamera.name === camera.name
                }
                onChange={() =>
                  setSelectedCamera(camera)
                }
              />

              <span>{camera.name}</span>
            </label>
          ))}
        </div>

        <header className="app-header">
          <h1 className="app-title">
            Face Recognition Attendance Dashboard
          </h1>

          <p className="app-subtitle">
            Live check-in/out, employee and visitor
            management, attendance analytics
          </p>
        </header>

        <main className="page-content">
          <Outlet
            context={{
              selectedCamera,
            }}
          />
        </main>
      </div>
    </div>
  );
}

export default Layout;