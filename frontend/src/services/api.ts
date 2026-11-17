import axios from 'axios';
import { Project, ProjectCreateInput } from '../types/project';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

export const projectService = {
  async getAll(): Promise<Project[]> {
    const res = await api.get<Project[]>('/projects/');
    return res.data;
  },
  async create(data: ProjectCreateInput): Promise<Project> {
    const res = await api.post<Project>('/projects/', data);
    return res.data;
  },
  async update(id: number, data: any): Promise<Project> {
    const res = await api.put<Project>(`/projects/${id}`, data);
    return res.data;
  },
  async delete(id: number): Promise<void> {
    await api.delete(`/projects/${id}`);
  },
  async duplicate(id: number): Promise<Project> {
    const res = await api.post<Project>(`/projects/${id}/duplicate`);
    return res.data;
  }
};
