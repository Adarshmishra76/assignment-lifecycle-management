import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { can, homeFor } from "./auth/permissions";
import Layout from "./components/Layout";
import { EmptyState, Spinner } from "./components/ui";
import { LookupProvider } from "./hooks/useLookups";
import Dashboard from "./pages/Dashboard";
import Courses from "./pages/Courses";
import Learners from "./pages/Learners";
import Assignments from "./pages/Assignments";
import RubricEditor from "./pages/RubricEditor";
import MyAssignments from "./pages/MyAssignments";
import Submissions, { SubmissionDetail } from "./pages/Submissions";
import Grading from "./pages/Grading";
import GradeDetail, { GradesList } from "./pages/Grades";
import Resubmissions from "./pages/Resubmissions";
import Appeals from "./pages/Appeals";
import Audit from "./pages/Audit";
import Datasets from "./pages/Datasets";
import DataQuality from "./pages/DataQuality";
import Login from "./pages/Login";

/** Client-side route guard. This only controls what is shown; the API still enforces every permission. */
function Guard({ allow, children }) {
  const { user, role, booting } = useAuth();
  const location = useLocation();
  if (booting) return <Spinner label="Restoring session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (allow && !allow(role)) return <Navigate to={homeFor(role)} replace />;
  return children;
}

function NotFound() {
  return <EmptyState title="Page not found">That address does not match any screen.</EmptyState>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><LookupProvider><Layout /></LookupProvider></Guard>}>
        <Route index element={<Guard allow={can.viewDashboard}><Dashboard /></Guard>} />
        <Route path="courses" element={<Courses />} />
        <Route path="learners" element={<Guard allow={can.viewLearners}><Learners /></Guard>} />
        <Route path="assignments" element={<Guard allow={can.manageAssignments}><Assignments /></Guard>} />
        <Route path="assignments/:id/rubric" element={<Guard allow={can.viewLearners}><RubricEditor /></Guard>} />
        <Route path="my-assignments" element={<Guard allow={can.submitWork}><MyAssignments /></Guard>} />
        <Route path="submissions" element={<Submissions />} />
        <Route path="submissions/:id" element={<SubmissionDetail />} />
        <Route path="grading" element={<Guard allow={can.grade}><Grading /></Guard>} />
        <Route path="grades" element={<GradesList />} />
        <Route path="grades/:submissionId" element={<GradeDetail />} />
        <Route path="resubmissions" element={<Resubmissions />} />
        <Route path="appeals" element={<Appeals />} />
        <Route path="audit" element={<Guard allow={can.viewAudit}><Audit /></Guard>} />
        <Route path="datasets" element={<Guard allow={can.manageDatasets}><Datasets /></Guard>} />
        <Route path="data-quality" element={<Guard allow={can.viewDataQuality}><DataQuality /></Guard>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
