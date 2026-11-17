/*
 * Configuração de execução do BIM SCHEDULE (lida antes da aplicação).
 *
 * Este arquivo NÃO é compilado: pode ser substituído no pacote instalado sem
 * recompilar o frontend. No aplicativo Windows (Electron), o handler do protocolo
 * app://bim-schedule gera este arquivo com o endereço e o token da sessão.
 * Valores já definidos em window.__BIM_SCHEDULE_CONFIG__ são preservados.
 *
 * Campos:
 *   apiBaseUrl  URL base da API (ex.: "http://127.0.0.1:8732/api/v1").
 *               Padrão: "/api/v1" (proxy do Vite em desenvolvimento).
 *   apiToken    Token local exigido pelo serviço quando LOCAL_API_TOKEN está definido.
 *   mode        "local" | "desktop" | "remote" (informativo).
 */
window.__BIM_SCHEDULE_CONFIG__ = Object.assign({}, window.__BIM_SCHEDULE_CONFIG__ || {});
