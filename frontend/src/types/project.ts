export interface Project {
  id: number;
  name: string;
  code: string;
  client?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  name: string;
  code: string;
  client?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
}
