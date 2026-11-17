/*
 * Configuração de execução do BIM SCHEDULE (lida antes da aplicação).
 *
 * Este arquivo NÃO é compilado: pode ser substituído no pacote instalado sem
 * recompilar o frontend. O aplicativo Windows (Electron) também pode definir
 * window.__BIM_SCHEDULE_CONFIG__ por um script de preload antes deste arquivo;
 * valores já definidos são preservados.
 *
 * Campos:
 *   apiBaseUrl  URL base da API (ex.: "http://127.0.0.1:8732/api/v1").
 *               Padrão: "/api/v1" (proxy do Vite em desenvolvimento).
 *   apiToken    Token local exigido pelo serviço quando LOCAL_API_TOKEN está definido.
 *   mode        "local" | "desktop" | "remote" (informativo).
 */
window.__BIM_SCHEDULE_CONFIG__ = Object.assign({}, window.__BIM_SCHEDULE_CONFIG__ || {});
