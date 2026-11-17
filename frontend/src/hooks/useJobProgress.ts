import { useCallback, useEffect, useState } from 'react';
import { jobService } from '../services/jobs';
import { getErrorMessage, toApiError } from '../services/apiClient';
import { Job } from '../types/api';

export const JOB_POLL_MS = 1_000;

export interface JobProgress {
  job: Job | null;
  error: string | null;
  cancelling: boolean;
  cancel: () => Promise<void>;
}

/** Acompanha uma tarefa do backend até ela terminar. */
export function useJobProgress(jobId: string | null, onFinished?: (job: Job) => void, pollMs = JOB_POLL_MS): JobProgress {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    setJob(null);
    setError(null);
    setCancelling(false);
    if (!jobId) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let stopped = false;

    const poll = async () => {
      try {
        const current = await jobService.get(jobId, controller.signal);
        if (stopped) return;
        setJob(current);
        setError(null);
        if (current.is_terminal) {
          onFinished?.(current);
          return;
        }
      } catch (err) {
        if (toApiError(err).kind === 'cancelled' || stopped) return;
        setError(getErrorMessage(err));
      }
      timer = window.setTimeout(poll, pollMs);
    };
    poll();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
    // onFinished intencionalmente fora das dependências: mudar o callback não reinicia o acompanhamento.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, pollMs]);

  const cancel = useCallback(async () => {
    if (!jobId) return;
    setCancelling(true);
    try {
      setJob(await jobService.cancel(jobId));
    } catch (err) {
      setError(getErrorMessage(err));
      setCancelling(false);
    }
  }, [jobId]);

  return { job, error, cancelling, cancel };
}
