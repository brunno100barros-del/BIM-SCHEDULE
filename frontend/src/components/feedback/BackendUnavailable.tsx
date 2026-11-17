import React from 'react';
import { PlugZap, RefreshCw, ExternalLink, Loader2 } from 'lucide-react';
import { getRuntimeConfig } from '../../config/runtime';

interface Props {
  checking: boolean;
  message?: string;
  onRetry: () => void;
}

/** Tela exibida quando o serviço local não responde. Nunca mostra dados simulados. */
export const BackendUnavailable: React.FC<Props> = ({ checking, message, onRetry }) => {
  const { apiBaseUrl } = getRuntimeConfig();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-xl w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-amber-500/15 text-amber-300 flex items-center justify-center"><PlugZap className="w-6 h-6" /></div>
          <div>
            <h1 className="text-lg font-bold">Serviço BIM SCHEDULE não encontrado</h1>
            <p className="text-xs text-slate-400">A aplicação precisa do serviço local para abrir e salvar projetos.</p>
          </div>
        </div>
        {message && <p className="text-sm text-slate-300 bg-slate-800 border border-slate-700 rounded-lg p-3">{message}</p>}
        <ol className="text-sm text-slate-300 list-decimal pl-5 space-y-1">
          <li>No Windows, execute <code className="text-blue-500">start.bat</code> na pasta do BIM SCHEDULE.</li>
          <li>Ou, em um terminal na pasta <code className="text-blue-500">backend</code>: <code className="text-blue-500">python -m app</code></li>
          <li>A verificação é repetida automaticamente a cada poucos segundos.</li>
        </ol>
        <p className="text-[11px] text-slate-500 font-mono break-all">Endereço configurado: {apiBaseUrl}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <button onClick={onRetry} disabled={checking} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-semibold flex items-center gap-2">
            {checking ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {checking ? 'Verificando…' : 'Tentar novamente'}
          </button>
          <a href="./demo.html" target="_blank" rel="noopener" className="px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-sm flex items-center gap-2 hover:bg-slate-700">
            <ExternalLink className="w-4 h-4" />Abrir demonstração (dados fictícios, sem serviço)
          </a>
        </div>
      </div>
    </div>
  );
};
