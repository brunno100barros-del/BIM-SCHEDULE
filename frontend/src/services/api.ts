/**
 * Ponto de importação único dos serviços de acesso ao backend.
 * Mantém `projectService` no mesmo caminho usado pelos módulos existentes.
 */
export { projectService } from './projects';
export { planningService } from './planning';
export { ifcService } from './ifc';
export { jobService } from './jobs';
export { systemService } from './system';
export { ApiError, getErrorMessage, toApiError } from './apiClient';
