import React, { useRef } from 'react';
import { WifiOff } from 'lucide-react';
import { AppShell } from './AppShell';
import { useBackendStatus } from '../hooks/useBackendStatus';
import { BackendUnavailable } from '../components/feedback/BackendUnavailable';
import { LoadingState } from '../components/feedback/StatusViews';

/**
 * Aplicação principal (versões local e Windows).
 *
 * - Verifica o serviço local antes de exibir os módulos.
 * - Sem serviço: mostra a tela de serviço indisponível (com acesso à demonstração estática).
 * - Se o serviço cair durante o uso: mantém a tela atual e exibe um aviso até reconectar.
 */
export function App() {
  const backend = useBackendStatus();
  const everOnline = useRef(false);
  if (backend.state === 'online') everOnline.current = true;

  if (!everOnline.current) {
    if (backend.state === 'checking' && !backend.error) {
      return <div className="min-h-screen bg-slate-950"><LoadingState message="Conectando ao serviço BIM SCHEDULE…" className="min-h-screen" /></div>;
    }
    return <BackendUnavailable checking={backend.state === 'checking'} message={backend.error?.message} onRetry={backend.retry} />;
  }

  const banner = backend.state === 'offline' ? (
    <div role="alert" className="px-6 py-2 bg-amber-500/15 border-b border-amber-500/30 text-amber-200 text-xs flex items-center gap-2">
      <WifiOff className="w-4 h-4" />
      <span className="flex-1">Conexão com o serviço local perdida. As alterações não serão salvas até a reconexão. Tentando novamente…</span>
      <button onClick={backend.retry} className="underline">Tentar agora</button>
    </div>
  ) : null;

  return <AppShell status={backend.status} banner={banner} />;
}

export default App;
