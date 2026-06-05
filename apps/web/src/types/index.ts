export type TabKey =
  | 'Landing'
  | 'BPM Model'
  | 'Generate Your Own Process'
  | 'Generate Real Data'
  | 'Mine Process'
  | 'SOPs'
  | 'Policies'
  | 'RAG Index'
  | 'AI Analysis'
  | 'Improve Process'
  | 'Agents';

export type ProcessNode = {
  id: string;
  label?: string;
  activity?: string;
  node_type?: string;
  system?: string;
  role?: string;
  is_control_point?: boolean;
  is_hidden?: boolean;
  is_bottleneck?: boolean;
  severity?: string;
  frequency?: number;
};

export type ProcessEdge = {
  id: string;
  source?: string;
  target?: string;
  source_activity?: string;
  target_activity?: string;
  label?: string;
  severity?: string;
  is_hidden?: boolean;
  is_bottleneck?: boolean;
  frequency?: number;
  avg_wait_hours?: number;
};

export type CustomGraphNode = {
  id: string;
  title: string;
  kind: string;
  lane: string;
  description: string;
};

export type CustomGraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
};

export type CustomProcessGraph = {
  title: string;
  summary: string;
  assumptions: string[];
  nodes: CustomGraphNode[];
  edges: CustomGraphEdge[];
};

export type IdealProcess = {
  id: string;
  name: string;
  nodes: ProcessNode[];
  edges: ProcessEdge[];
};

export type EventLog = {
  id: string;
  filename: string;
  row_count: number;
  case_count: number;
  hidden_step_count: number;
  date_start: string | null;
  date_end: string | null;
  metadata: Record<string, unknown>;
  preview?: Record<string, unknown>[];
  download_url: string;
};

export type MiningRun = {
  id: string;
  metrics: Record<string, unknown>;
  top_variants: { variant: string[]; count: number; share: number }[];
  top_hidden_issues: { issue: string; count: number }[];
  top_bottlenecks: { source: string; target: string; avg_wait_hours: number; frequency: number }[];
  nodes: ProcessNode[];
  edges: ProcessEdge[];
};

export type DocumentSummary = {
  id: string;
  title: string;
  source_type: string;
  source_file_path: string;
  source_repository: string;
  content?: string;
  metadata: Record<string, unknown>;
};

export type RagChunk = {
  chunk_id: string;
  document_title: string;
  title: string;
  source_type: string;
  source_file_path: string;
  source_repository: string;
  chunk_index: number;
  embedding_dimensions: number;
  embedding_preview: number[];
  embedding?: number[];
  metadata: Record<string, unknown>;
  chunk_text: string;
  similarity?: number;
};

export type Proposal = {
  id: string;
  title: string;
  problem_statement: string;
  evidence: string[];
  expected_impact: string;
  risk_level: string;
  required_approvers: string[];
  monitoring_kpis: string[];
  actions: ImprovementAction[];
};

export type ImprovementAction = {
  id: string;
  proposal_id: string;
  title: string;
  target_system: string;
  action_type: string;
  description: string;
  preconditions: string[];
  approval_status: string;
  approved_by?: string;
  approval_comment?: string;
};

export type AgentRun = {
  id: string;
  action_id: string;
  status: string;
  validation_result: Record<string, unknown>;
  config_json: Record<string, unknown>;
  steps: {
    id: string;
    step_order: number;
    name: string;
    status: string;
    input_json: Record<string, unknown>;
    output_json: Record<string, unknown>;
    explanation: string;
  }[];
};
