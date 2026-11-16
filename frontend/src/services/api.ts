import axios from 'axios';
import { Project, ProjectCreateInput, ProjectUpdateInput } from '../types/project';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const projectService = {
  async getAll(): Promise<Project[]> {
    const response = await api.get<Project[]>('/projects/');
    return response.data;
  },

  async getById(id: number): Promise<Project> {
    const response = await api.get<Project>(`/projects/${id}`);
    return response.data;
  },

  async create(data: ProjectCreateInput): Promise<Project> {
    const response = await api.post<Project>('/projects/', data);
    return response.data;
  },

  async update(id: number, data: ProjectUpdateInput): Promise<Project> {
    const response = await api.put<Project>(`/projects/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/projects/${id}`);
  },

  async duplicate(id: number): Promise<Project> {
    const response = await api.post<Project>(`/projects/${id}/duplicate`);
    return response.data;
  }
};
