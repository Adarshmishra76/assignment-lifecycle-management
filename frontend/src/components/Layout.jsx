import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { NAV, ROLES } from "../auth/permissions";

export default function Layout() {
  const { user, role, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const items = NAV.filter((n) => n.show(role));

  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-0.5 p-3">
      {items.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === "/"}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            `rounded-md px-3 py-2 text-sm ${isActive ? "bg-white/15 font-medium text-white" : "text-ink-300 hover:bg-white/10 hover:text-white"}`
          }
        >
          {n.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <header className="flex items-center justify-between bg-ink-900 px-4 py-3 text-white lg:hidden">
        <span className="font-serif text-lg font-semibold">Gradebook</span>
        <button className="btn border border-white/30" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          Menu
        </button>
      </header>

      <aside className={`${open ? "block" : "hidden"} bg-ink-900 lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col`}>
        <div className="hidden px-6 pb-2 pt-6 font-serif text-xl font-semibold text-white lg:block">Gradebook</div>
        <div className="flex-1 overflow-y-auto">{nav}</div>
        <div className="border-t border-white/10 p-4 text-sm text-ink-300">
          <p className="truncate font-medium text-white">{user?.full_name}</p>
          <p>{ROLES[role] || role}</p>
          <button onClick={logout} className="mt-2 underline underline-offset-2 hover:text-white">
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 p-4 sm:p-8">
        <Outlet />
      </main>
    </div>
  );
}
