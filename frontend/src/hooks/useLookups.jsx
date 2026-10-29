import { createContext, useContext, useMemo } from "react";
import { assignmentsApi, coursesApi, learnersApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { useApi } from "./useApi";

const Ctx = createContext(null);
const byId = (page) => Object.fromEntries((page?.items || []).map((i) => [i.id, i]));

/** id -> record maps (first 100 of each) so tables show names; anything beyond falls back to "#id". */
export function LookupProvider({ children }) {
  const { user, role } = useAuth();
  const courses = useApi(() => coursesApi.list({ page_size: 100 }), [user?.id]);
  const assignments = useApi(() => assignmentsApi.list({ page_size: 100 }), [user?.id]);
  const learners = useApi(() => learnersApi.list({ page_size: 100 }), [user?.id], { enabled: can.viewLearners(role) });

  const value = useMemo(() => {
    const c = byId(courses.data), a = byId(assignments.data), l = byId(learners.data);
    return {
      courses: courses.data?.items || [],
      assignments: assignments.data?.items || [],
      learners: learners.data?.items || [],
      courseName: (id) => (c[id] ? `${c[id].code} · ${c[id].title}` : `Course #${id}`),
      courseCode: (id) => c[id]?.code || `#${id}`,
      assignmentTitle: (id) => a[id]?.title || `Assignment #${id}`,
      learnerName: (id) => l[id]?.full_name || l[id]?.student_number || `Learner #${id}`,
      refresh: () => { courses.reload(); assignments.reload(); learners.reload(); },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courses.data, assignments.data, learners.data]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useLookups = () => useContext(Ctx);
