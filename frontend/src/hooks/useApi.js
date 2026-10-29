import { useCallback, useEffect, useRef, useState } from "react";

/** Run an async API call and expose { data, loading, error, reload }. Re-runs when deps change. */
export function useApi(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);

  const run = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    return fnRef.current()
      .then((data) => id === seq.current && setState({ data, loading: false, error: null }))
      .catch((error) => id === seq.current && setState({ data: null, loading: false, error }));
  }, []);

  useEffect(() => {
    if (enabled) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  return { ...state, reload: run };
}

/** Paginated list helper: keeps page/pageSize/filters and refetches (page resets on filter change). */
export function usePaged(fetcher, initialFilters = {}, { pageSize = 20, enabled = true } = {}) {
  const [page, setPage] = useState(1);
  const [filters, setFiltersState] = useState(initialFilters);
  const setFilters = useCallback((next) => {
    setPage(1);
    setFiltersState((f) => ({ ...f, ...next }));
  }, []);
  const clean = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v != null));
  const key = JSON.stringify(clean);
  const result = useApi(() => fetcher({ ...clean, page, page_size: pageSize }), [page, key, pageSize], { enabled });
  return { ...result, page, setPage, pageSize, filters, setFilters };
}
