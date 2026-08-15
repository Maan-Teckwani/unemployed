"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import { api, type PipelineKind, type PipelineRun } from "@/lib/api";

/**
 * The one long-running thing this app does, hoisted out of the page that starts
 * it.
 *
 * Fetching takes about ten minutes. When the only progress bar lived on the home
 * page, starting a run meant either staring at that page or navigating away and
 * losing every signal that anything was happening — so the run felt like it had
 * stalled, and the natural response was to start it again. Holding the state up
 * here lets the nav carry a thin progress bar on every page, and means the
 * button and the bar are reading the same poll rather than two of their own.
 */

type PipelineContext = {
  run: PipelineRun | null;
  running: boolean;
  start: (kind: PipelineKind) => Promise<void>;
  /** Increments when a run finishes, so pages can refetch what it changed. */
  finished: number;
};

const Ctx = createContext<PipelineContext | null>(null);

export function usePipeline(): PipelineContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("usePipeline must be used inside <PipelineProvider>");
  return ctx;
}

/** While something is running the bar has to move; idle, this is just a heartbeat. */
const POLL_RUNNING = 2000;
const POLL_IDLE = 15000;

export function PipelineProvider({ children }: { children: React.ReactNode }) {
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [finished, setFinished] = useState(0);
  const wasRunning = useRef(false);

  const running = run?.status === "running";

  const poll = useCallback(async () => {
    try {
      const current = await api.pipelineStatus();
      setRun(current);
      if (wasRunning.current && current?.status !== "running") {
        wasRunning.current = false;
        if (current?.status === "failed") toast.error(current.error ?? "Run failed");
        else toast.success("Finished");
        setFinished((n) => n + 1);
      }
      wasRunning.current = current?.status === "running";
    } catch {
      /* backend not reachable */
    }
  }, []);

  useEffect(() => {
    poll();
    const timer = setInterval(poll, running ? POLL_RUNNING : POLL_IDLE);
    return () => clearInterval(timer);
  }, [poll, running]);

  const start = useCallback(async (kind: PipelineKind) => {
    try {
      setRun(await api.startPipeline(kind));
      wasRunning.current = true;
    } catch (e) {
      toast.error(String(e).includes("409") ? "Something is already running" : String(e));
    }
  }, []);

  const value = useMemo(
    () => ({ run, running, start, finished }),
    [run, running, start, finished],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
