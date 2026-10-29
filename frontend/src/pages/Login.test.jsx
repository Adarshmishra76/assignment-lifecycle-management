import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ login: vi.fn(), user: null }));
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: mocks.user, login: mocks.login }) }));

import Login from "./Login";

function renderLogin(initialEntry = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<p>Dashboard page</p>} />
        <Route path="/my-assignments" element={<p>My assignments page</p>} />
        <Route path="/grades" element={<p>Grades page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const fill = async (user, email = "ada@demo.local", password = "DemoPass123!") => {
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
};

describe("Login", () => {
  it("keeps the button disabled until both fields are filled", async () => {
    mocks.user = null;
    const user = userEvent.setup();
    renderLogin();
    const button = screen.getByRole("button", { name: "Sign in" });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Email"), "ada@demo.local");
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Password"), "x");
    expect(button).toBeEnabled();
  });

  it("signs in and goes to the dashboard for staff", async () => {
    mocks.user = null;
    mocks.login.mockResolvedValue({ role: "instructor" });
    const user = userEvent.setup();
    renderLogin();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(mocks.login).toHaveBeenCalledWith("ada@demo.local", "DemoPass123!");
    expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
  });

  it("sends learners to their assignments", async () => {
    mocks.user = null;
    mocks.login.mockResolvedValue({ role: "learner" });
    const user = userEvent.setup();
    renderLogin();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("My assignments page")).toBeInTheDocument();
  });

  it("returns to the page the visitor originally asked for", async () => {
    mocks.user = null;
    mocks.login.mockResolvedValue({ role: "learner" });
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[{ pathname: "/login", state: { from: "/grades" } }]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/grades" element={<p>Grades page</p>} />
        </Routes>
      </MemoryRouter>
    );
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Grades page")).toBeInTheDocument();
  });

  it("shows a friendly message for a wrong password", async () => {
    mocks.user = null;
    mocks.login.mockRejectedValue({ status: 401, message: "Invalid email or password" });
    const user = userEvent.setup();
    renderLogin();
    await fill(user, "ada@demo.local", "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("shows the server message for other failures", async () => {
    mocks.user = null;
    mocks.login.mockRejectedValue({ status: 0, message: "Cannot reach the server." });
    const user = userEvent.setup();
    renderLogin();
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the server."));
  });

  it("skips the form when already signed in", async () => {
    mocks.user = { role: "learner" };
    renderLogin();
    expect(await screen.findByText("My assignments page")).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });
});
