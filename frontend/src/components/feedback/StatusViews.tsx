import React from 'react';
import { AlertCircle, CheckCircle2, Info, Loader2, RefreshCw } from 'lucide-react';

/** Estados padronizados de carregamento, erro, vazio e aviso, no visual atual da aplicação. */

export const LoadingState: React.FC<{ message?: string; className?: string }> = ({ message = 'Carregando…', className = '' }) => (
  <div role="status" aria-live="polite" className={`flex items-center justify-center gap-2 py-12 text-sm text-slate-400 ${className}`}>
    <Loader2 className="w-4 h-4 animate-spin" />
    <span>{message}</span>
  </div>
);

export const ErrorState: React.FC<{ message: string; onRetry?: () => void; title?: string }> = ({ message, onRetry, title = 'Não foi possível concluir a operação' }) => (
  <div role="alert" className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm flex items-start gap-3">
    <AlertCircle className="w-5 h-5 shrink-0 text-red-400 mt-0.5" />
    <div className="flex-1 min-w-0">
      <p className="font-semibold text-red-200">{title}</p>
      <p className="mt-1 text-red-300/90 break-words">{message}</p>
    </div>
    {onRetry && (
      <button onClick={onRetry} className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-100 text-xs font-semibold flex items-center gap-1.5 shrink-0">
        <RefreshCw className="w-3.5 h-3.5" />Tentar novamente
      </button>
    )}
  </div>
);

export const EmptyState: React.FC<{ message: string; action?: React.ReactNode }> = ({ message, action }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
    <p className="text-slate-400">{message}</p>
    {action}
  </div>
);

export type NoticeTone = 'success' | 'error' | 'info';

const TONES: Record<NoticeTone, { box: string; icon: React.ElementType }> = {
  success: { box: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300', icon: CheckCircle2 },
  error: { box: 'bg-red-500/10 border-red-500/30 text-red-300', icon: AlertCircle },
  info: { box: 'bg-blue-500/10 border-blue-500/30 text-blue-200', icon: Info },
};

export const Notice: React.FC<{ tone: NoticeTone; children: React.ReactNode; onDismiss?: () => void }> = ({ tone, children, onDismiss }) => {
  const { box, icon: Icon } = TONES[tone];
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`p-3 rounded-lg border text-sm flex items-start gap-2 ${box}`}>
      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0 break-words">{children}</div>
      {onDismiss && <button onClick={onDismiss} aria-label="Fechar aviso" className="opacity-70 hover:opacity-100 text-xs">✕</button>}
    </div>
  );
};
