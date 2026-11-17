import React from 'react';
import { Loader2, XCircle } from 'lucide-react';
import { Job } from '../../types/api';

const LABELS: Record<string, string> = {
  queued: 'Na fila',
  running: 'Em execução',
  cancelling: 'Cancelando…',
  completed: 'Concluída',
  failed: 'Falhou',
  cancelled: 'Cancelada',
  interrupted: 'Interrompida',
};

interface Props {
  title: string;
  job: Job | null;
  error?: string | null;
  cancelling?: boolean;
  onCancel?: () => void;
}

/** Progresso de uma tarefa do backend, com cancelamento enquanto estiver ativa. */
export const JobProgressCard: React.FC<Props> = ({ title, job, error, cancelling, onCancel }) => {
  const active = !!job && !job.is_terminal;
  const failed = job?.status === 'failed' || job?.status === 'interrupted';
  return (
    <div className="p-3 rounded-lg bg-slate-800 border border-slate-700 text-xs space-y-2" aria-live="polite">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-200 truncate flex items-center gap-1.5">
          {active && <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />}
          {title}
        </span>
        <span className={failed ? 'text-red-300' : 'text-slate-400'}>{job ? LABELS[job.status] ?? job.status : 'Consultando…'}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job?.progress ?? 0}>
        <div className={`h-full transition-all ${failed ? 'bg-red-500' : 'bg-blue-500'}`} style={{ width: `${job?.progress ?? 0}%` }} />
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-500 truncate">{job?.error || job?.message || ''}</span>
        {active && onCancel && (
          <button onClick={onCancel} disabled={cancelling || job?.status === 'cancelling'} className="text-red-300 hover:text-red-200 disabled:opacity-50 flex items-center gap-1 shrink-0">
            <XCircle className="w-3.5 h-3.5" />Cancelar
          </button>
        )}
      </div>
      {error && <p className="text-red-300">{error}</p>}
    </div>
  );
};
