import { useCallback, useEffect, useRef, useState } from 'react';
import { systemService } from '../services/system';
import { ApiError, toApiError } from '../services/apiClient';
import { SystemStatus } from '../types/api';

export type BackendState = 'checking' | 'online' | 'offline';

export interface BackendStatus {
  state: BackendState;
  status: SystemStatus | null;
  error: ApiError | null;
  lastCheckedAt: Date | null;
  retry: () => void;
}

/** Intervalos de verificação: mais espaçados com o serviço disponível. */
export const ONLINE_POLL_MS = 15_000;
export const OFFLINE_POLL_MS = 3_000;

/**
 * Acompanha a disponibilidade do serviço local. Quando o serviço cai, a
 * verificação fica mais frequente para reconectar assim que ele voltar.
 */
export function useBackendStatus(onlinePollMs = ONLINE_POLL_MS, offlinePollMs = OFFLINE_POLL_MS): BackendStatus {
  const [state, setState] = useState<BackendState>('checking');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [tick, setTick] = useState(0);
  const stateRef = useRef<BackendState>('checking');

  const retry = useCallback(() => {
    stateRef.current = stateRef.current === 'online' ? 'online' : 'checking';
    setState(stateRef.current);
    setTick((t) => t + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    systemService
      .status(controller.signal)
      .then((data) => {
        stateRef.current = 'online';
        setStatus(data);
        setError(null);
        setState('online');
      })
      .catch((err) => {
        const apiError = toApiError(err);
        if (apiError.kind === 'cancelled') return;
        stateRef.current = 'offline';
        setError(apiError);
        setState('offline');
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setLastCheckedAt(new Date());
        const delay = stateRef.current === 'online' ? onlinePollMs : offlinePollMs;
        timer = window.setTimeout(() => setTick((t) => t + 1), delay);
      });
    return () => {
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [tick, onlinePollMs, offlinePollMs]);

  return { state, status, error, lastCheckedAt, retry };
}
