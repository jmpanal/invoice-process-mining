import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { apiGet, apiPost, API_URL } from './api/client';
import BeautifulProcessGraph from './components/BeautifulProcessGraph';
import BpmnProcessView from './components/BpmnProcessView';
import GraphView from './components/GraphView';
import { AgentRun, CustomProcessGraph, DocumentSummary, EventLog, IdealProcess, ImprovementAction, MiningRun, Proposal, RagChunk, TabKey } from './types';

const TABS: TabKey[] = [
  'Landing',
  'BPM Model',
  'Generate Your Own Process',
  'Generate Real Data',
  'Mine Process',
  'SOPs',
  'Policies',
  'RAG Index',
  'AI Analysis',
  'Improve Process',
  'Agents',
];

function getInitialTab(): TabKey {
  const hashTab = decodeURIComponent(window.location.hash.replace(/^#/, ''));
  return TABS.includes(hashTab as TabKey) ? (hashTab as TabKey) : 'Landing';
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>(getInitialTab);
  const [status, setStatus] = useState('checking');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [idealProcess, setIdealProcess] = useState<IdealProcess | null>(null);
  const [idealProcesses, setIdealProcesses] = useState<IdealProcess[]>([]);
  const [eventLogs, setEventLogs] = useState<EventLog[]>([]);
  const [selectedProcessId, setSelectedProcessId] = useState('');
  const [selectedLogId, setSelectedLogId] = useState('');
  const [caseCount, setCaseCount] = useState(2000);
  const [seed, setSeed] = useState(42);
  const [latestLog, setLatestLog] = useState<EventLog | null>(null);
  const [miningRun, setMiningRun] = useState<MiningRun | null>(null);
  const [miningRuns, setMiningRuns] = useState<MiningRun[]>([]);
  const [sops, setSops] = useState<DocumentSummary[]>([]);
  const [policies, setPolicies] = useState<DocumentSummary[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [selectedDocumentChunks, setSelectedDocumentChunks] = useState<RagChunk[]>([]);
  const [ragStatus, setRagStatus] = useState<Record<string, unknown>>({});
  const [ragQuery, setRagQuery] = useState('What can we automate safely?');
  const [ragResults, setRagResults] = useState<Record<string, unknown>[]>([]);
  const [aiQuestion, setAiQuestion] = useState('Why are invoices delayed and what can we automate safely?');
  const [aiAnswer, setAiAnswer] = useState<Record<string, unknown> | null>(null);
  const [proposalResult, setProposalResult] = useState<Record<string, unknown> | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [actions, setActions] = useState<ImprovementAction[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [customProcessDescription, setCustomProcessDescription] = useState('Employee onboarding for a remote software engineer');
  const [customProcessGraph, setCustomProcessGraph] = useState<CustomProcessGraph | null>(null);

  const selectedLog = eventLogs.find((log) => log.id === selectedLogId);
  const latestMiningId = miningRun?.id || miningRuns[0]?.id || '';
  const approvedActions = actions.filter((action) => action.approval_status === 'approved');

  useEffect(() => {
    void refreshAll();
  }, []);

  async function runTask<T>(label: string, task: () => Promise<T>): Promise<T | null> {
    setBusy(label);
    setError('');
    try {
      return await task();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    } finally {
      setBusy('');
    }
  }

  async function refreshAll() {
    await runTask('refresh', async () => {
      const health = await apiGet<{ status: string }>('/health');
      setStatus(health.status);
      const [processList, logs, runs, sopDocs, policyDocs, rag, proposalList, actionList, runList] = await Promise.all([
        apiGet<IdealProcess[]>('/bpm/ideal-processes').catch(() => []),
        apiGet<EventLog[]>('/data/event-logs').catch(() => []),
        apiGet<MiningRun[]>('/mining/runs').catch(() => []),
        apiGet<DocumentSummary[]>('/documents?source_type=SOP').catch(() => []),
        apiGet<DocumentSummary[]>('/documents?source_type=POLICY').catch(() => []),
        apiGet<Record<string, unknown>>('/rag/status').catch(() => ({})),
        apiGet<Proposal[]>('/improvements/proposals').catch(() => []),
        apiGet<ImprovementAction[]>('/improvements/actions').catch(() => []),
        apiGet<AgentRun[]>('/agents/runs').catch(() => []),
      ]);
      setIdealProcesses(processList);
      setEventLogs(logs);
      setMiningRuns(runs);
      setSops(sopDocs);
      setPolicies(policyDocs);
      setRagStatus(rag);
      setProposals(proposalList);
      setActions(actionList);
      setAgentRuns(runList);
      if (processList[0] && !selectedProcessId) setSelectedProcessId(processList[0].id);
      const latestProcess = await apiGet<IdealProcess>('/bpm/ideal-process/latest').catch(() => null);
      if (latestProcess?.nodes?.length) setIdealProcess(latestProcess);
      if (logs[0] && !selectedLogId) setSelectedLogId(logs[0].id);
      if (runs[0] && !miningRun) setMiningRun(runs[0]);
      if (runList[0] && !selectedRun) setSelectedRun(runList[0]);
    });
  }

  async function generateIdealProcess() {
    const result = await runTask('generate-bpm', () => apiPost<IdealProcess>('/bpm/generate-invoice-process'));
    if (result) {
      setIdealProcess(result);
      setSelectedProcessId(result.id);
      await refreshAll();
    }
  }

  async function generateEvents(useDefaults = false) {
    const result = await runTask('generate-events', () =>
      apiPost<EventLog>('/data/generate-invoice-events', { case_count: useDefaults ? 2000 : caseCount, seed: useDefaults ? 42 : seed }),
    );
    if (result) {
      setLatestLog(result);
      setSelectedLogId(result.id);
      await refreshAll();
    }
  }

  async function uploadLog(file: File | undefined) {
    if (!file) return;
    const body = new FormData();
    body.append('file', file);
    const result = await runTask('upload-log', () => apiPost<EventLog>('/data/upload-event-log', body));
    if (result) {
      setLatestLog(result);
      setSelectedLogId(result.id);
      await refreshAll();
    }
  }

  async function mineProcess() {
    const result = await runTask('mine', () => apiPost<MiningRun>('/mining/run', { ideal_process_id: selectedProcessId, event_log_id: selectedLogId }));
    if (result) {
      setMiningRun(result);
      await refreshAll();
    }
  }

  async function generateDocs(kind: 'sops' | 'policies') {
    const path = kind === 'sops' ? '/documents/generate-sops' : '/documents/generate-policies';
    const result = await runTask(`generate-${kind}`, () => apiPost<DocumentSummary[]>(path));
    if (result) {
      if (kind === 'sops') setSops(result);
      else setPolicies(result);
      await refreshAll();
    }
  }

  async function openDocument(document: DocumentSummary) {
    const result = await runTask('document', () => apiGet<DocumentSummary>(`/documents/${document.id}`));
    if (result) {
      setSelectedDocument(result);
      const chunks = await runTask('document-chunks', () => apiGet<RagChunk[]>(`/rag/chunks?source_file_path=${encodeURIComponent(result.source_file_path)}`));
      setSelectedDocumentChunks(chunks || []);
    }
  }

  async function rebuildRag() {
    const result = await runTask('rag-reindex', () => apiPost<Record<string, unknown>>('/rag/reindex'));
    if (result) setRagStatus(result);
  }

  async function searchRag() {
    const result = await runTask('rag-search', () => apiPost<Record<string, unknown>[]>('/rag/search', { query: ragQuery, top_k: 5, filters: {} }));
    if (result) setRagResults(result);
  }

  async function askAi(question = aiQuestion) {
    setAiQuestion(question);
    const result = await runTask('ai-analyze', () => apiPost<Record<string, unknown>>('/ai/analyze', { question, mining_run_id: latestMiningId || null }));
    if (result) setAiAnswer(result);
  }

  async function generateImprovements() {
    if (!latestMiningId) {
      setError('Mine a process first.');
      return;
    }
    const result = await runTask('improvements', () => apiPost<Record<string, unknown>>('/improvements/generate', { mining_run_id: latestMiningId }));
    if (result) {
      setProposalResult(result);
      await refreshAll();
    }
  }

  async function updateApproval(action: ImprovementAction, approve: boolean) {
    const name = window.prompt(approve ? 'Approver name' : 'Reviewer name', approve ? 'Finance Controller' : 'Process Owner');
    if (!name) return;
    const comment = window.prompt('Comment', approve ? 'Approved for mock execution.' : 'Rejected for demo review.') || '';
    const path = approve ? `/improvements/actions/${action.id}/approve` : `/improvements/actions/${action.id}/reject`;
    const body = approve ? { approved_by: name, comment } : { rejected_by: name, comment };
    await runTask('approval', () => apiPost<ImprovementAction>(path, body));
    await refreshAll();
  }

  async function runAgent(action: ImprovementAction) {
    setSelectedRun(null);
    const result = await runTask('agent', () => apiPost<AgentRun>(`/agents/run-action/${action.id}`));
    if (result) {
      setSelectedRun(result);
      await refreshAll();
    }
  }

  async function generateCustomProcess() {
    const result = await runTask('custom-process', () => apiPost<CustomProcessGraph>('/custom-process/generate', { description: customProcessDescription }));
    if (result) setCustomProcessGraph(result);
  }

  function selectTab(tab: TabKey) {
    setActiveTab(tab);
    window.history.replaceState(null, '', `#${encodeURIComponent(tab)}`);
  }

  const page = useMemo(() => {
    switch (activeTab) {
      case 'Landing':
        return <Landing onDefaults={() => void generateEvents(true)} />;
      case 'BPM Model':
        return <BpmPage process={idealProcess?.nodes?.length ? idealProcess : null} onGenerate={() => void generateIdealProcess()} />;
      case 'Generate Your Own Process':
        return (
          <CustomProcessPage
            description={customProcessDescription}
            graph={customProcessGraph}
            onDescription={setCustomProcessDescription}
            onGenerate={() => void generateCustomProcess()}
          />
        );
      case 'Generate Real Data':
        return (
          <DataPage
            caseCount={caseCount}
            seed={seed}
            onCaseCount={setCaseCount}
            onSeed={setSeed}
            onGenerate={() => void generateEvents()}
            onDefaults={() => void generateEvents(true)}
            onUpload={(file) => void uploadLog(file)}
            latestLog={latestLog || eventLogs[0] || null}
          />
        );
      case 'Mine Process':
        return (
          <MinePage
            processes={idealProcesses}
            eventLogs={eventLogs}
            selectedProcessId={selectedProcessId}
            selectedLogId={selectedLogId}
            selectedLog={selectedLog || null}
            onProcess={setSelectedProcessId}
            onLog={setSelectedLogId}
            onMine={() => void mineProcess()}
            miningRun={miningRun}
          />
        );
      case 'SOPs':
        return <DocumentsPage title="SOPs" documents={sops} selected={selectedDocument} chunks={selectedDocumentChunks} onGenerate={() => void generateDocs('sops')} onOpen={(doc) => void openDocument(doc)} />;
      case 'Policies':
        return <DocumentsPage title="Policies" documents={policies} selected={selectedDocument} chunks={selectedDocumentChunks} onGenerate={() => void generateDocs('policies')} onOpen={(doc) => void openDocument(doc)} />;
      case 'RAG Index':
        return <RagPage status={ragStatus} query={ragQuery} results={ragResults} onQuery={setRagQuery} onReindex={() => void rebuildRag()} onSearch={() => void searchRag()} />;
      case 'AI Analysis':
        return <AiPage question={aiQuestion} answer={aiAnswer} onQuestion={setAiQuestion} onAsk={() => void askAi()} onCanned={(question) => void askAi(question)} />;
      case 'Improve Process':
        return (
          <ImprovePage
            proposalResult={proposalResult}
            proposals={proposals}
            onGenerate={() => void generateImprovements()}
            onApprove={(action) => void updateApproval(action, true)}
            onReject={(action) => void updateApproval(action, false)}
          />
        );
      case 'Agents':
        return <AgentsPage actions={approvedActions} runs={agentRuns} selectedRun={selectedRun} onRun={(action) => void runAgent(action)} onSelect={setSelectedRun} />;
    }
  }, [
    activeTab,
    actions,
    aiAnswer,
    aiQuestion,
    caseCount,
    eventLogs,
    idealProcess,
    idealProcesses,
    latestLog,
    miningRun,
    policies,
    proposalResult,
    proposals,
    ragQuery,
    ragResults,
    ragStatus,
    seed,
    selectedDocument,
    selectedDocumentChunks,
    selectedLog,
    selectedLogId,
    selectedProcessId,
    sops,
    agentRuns,
    approvedActions,
    customProcessDescription,
    customProcessGraph,
    selectedRun,
  ]);

  return (
    <div className="min-h-screen bg-white text-neutral-950">
      <header className="border-b border-neutral-300">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-6 py-4">
          <div>
            <div className="text-lg font-semibold">Invoice Process Intelligence Lab</div>
            <div className="text-xs text-neutral-500">Backend status: {status}</div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            {busy ? <span className="badge badge-orange">Running {busy}</span> : <span className="badge badge-green">Idle</span>}
            <button className="border border-neutral-900 px-3 py-1" onClick={() => void refreshAll()}>
              Refresh
            </button>
          </div>
        </div>
        <nav className="mx-auto grid max-w-[1500px] grid-cols-5 border-t border-neutral-200 text-sm lg:grid-cols-10">
          {TABS.map((tab) => (
            <button
              key={tab}
              className={`border-r border-neutral-200 px-3 py-3 text-left ${activeTab === tab ? 'bg-neutral-950 text-white' : 'bg-white text-neutral-800'}`}
              onClick={() => selectTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-[1500px] px-6 py-6">
        {error ? <div className="mb-4 border border-red-700 p-3 text-sm text-red-800">{error}</div> : null}
        {page}
      </main>
    </div>
  );
}

function Landing({ onDefaults }: { onDefaults: () => void }) {
  const systems = [
    ['Coupa', 'invoice intake'],
    ['SAP S/4HANA', 'purchase order, goods receipt, payment block, payment scheduling'],
    ['ServiceNow', 'exception tickets and escalations'],
    ['Vendor Master Data', 'vendor risk and compliance status'],
    ['Payment System', 'payment scheduling and remittance'],
    ['Email and Excel', 'hidden shadow process'],
    ['PostgreSQL + pgvector', 'structured memory and vector search'],
    ['OpenAI', 'grounded analysis and improvement proposals'],
    ['Mock Agents', 'approved configuration generation'],
  ];
  const flow = ['Ideal BPM process', 'Real event log', 'Process mining', 'SOPs and policies', 'RAG index', 'AI analysis', 'Improvement proposals', 'Human approval', 'Agent execution'];
  return (
    <section className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
        <div>
          <h1 className="max-w-4xl text-5xl font-semibold leading-tight">Invoice Process Intelligence Lab</h1>
          <p className="mt-4 max-w-3xl text-lg text-neutral-700">
            A local demo showing how BPM, process mining, RAG, AI analysis, human approval, and mock agents can improve invoice handling safely.
          </p>
          <div className="mt-6 flex gap-3">
            <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={onDefaults}>
              Use demo defaults
            </button>
            <span className="self-center text-sm text-neutral-600">Synthetic data. Mock integrations. No real enterprise APIs.</span>
          </div>
        </div>
        <div className="panel p-4">
          <h2 className="text-lg font-semibold">Demo Script</h2>
          <ol className="mt-3 space-y-2 text-sm text-neutral-700">
            {['Generate ideal invoice process', 'Generate 2,000 invoice cases with seed 42', 'Mine the process', 'Generate SOPs', 'Generate policies', 'Rebuild RAG index', 'Ask why invoices are delayed', 'Generate improvements', 'Approve one action', 'Run agent', 'Inspect mock config JSON'].map((item) => (
              <li key={item} className="border-b border-neutral-200 pb-2">
                {item}
              </li>
            ))}
          </ol>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {systems.map(([name, description]) => (
          <div key={name} className={`panel min-h-[110px] p-4 ${name === 'Email and Excel' ? 'border-red-700' : ''}`}>
            <div className="text-base font-semibold">{name}</div>
            <div className="mt-2 text-sm text-neutral-600">{description}</div>
            {name === 'Email and Excel' ? <div className="mt-3 badge badge-red">Hidden risk path</div> : null}
          </div>
        ))}
      </div>
      <div className="panel p-4">
        <h2 className="text-lg font-semibold">Product Flow</h2>
        <div className="mt-4 grid gap-2 md:grid-cols-9">
          {flow.map((item, index) => (
            <div key={item} className="flex items-center gap-2">
              <div className="min-h-[78px] flex-1 border border-neutral-300 p-3 text-sm">{item}</div>
              {index < flow.length - 1 ? <div className="hidden text-neutral-400 md:block">→</div> : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BpmPage({ process, onGenerate }: { process: IdealProcess | null; onGenerate: () => void }) {
  const nodes = process?.nodes ?? [];
  const edges = process?.edges ?? [];
  const controlNodes = nodes.filter((node) => node.is_control_point);
  return (
    <section className="space-y-4">
      <PageTitle title="BPM Model" text="Canonical governed process. Hidden shadow steps are excluded." />
      <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={onGenerate}>
        Generate ideal invoice process
      </button>
      {process && nodes.length ? (
        <>
          <MetricGrid
            items={[
              ['Nodes', nodes.length],
              ['Edges', edges.length],
              ['Control points', controlNodes.length],
            ]}
          />
          <BpmnProcessView nodes={nodes} edges={edges} />
          <div className="grid gap-3 md:grid-cols-4">
            {controlNodes.map((node) => (
              <div key={node.id} className="panel p-3 text-sm">
                <div className="font-semibold">{node.label}</div>
                <div className="mt-1 text-neutral-600">{node.system}</div>
                <span className="badge mt-2 inline-block">Control point</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <EmptyState text="Generate the canonical invoice process first." />
      )}
    </section>
  );
}

function CustomProcessPage(props: {
  description: string;
  graph: CustomProcessGraph | null;
  onDescription: (value: string) => void;
  onGenerate: () => void;
}) {
  return (
    <section className="space-y-4">
      <PageTitle
        title="Generate Your Own Process"
        text="Describe any process at a high level or in detail. The generator expands high-level requests into likely operational steps and renders an editable n8n-style graph."
      />
      <div className="panel p-4">
        <label className="text-sm font-semibold">
          Process description
          <textarea
            className="mt-2 min-h-[130px] w-full border border-neutral-300 px-3 py-2 text-sm"
            value={props.description}
            onChange={(event) => props.onDescription(event.target.value)}
            placeholder="Example: Customer refund handling for an ecommerce company with fraud checks and finance approval."
          />
        </label>
        <div className="mt-3 flex justify-end">
          <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onGenerate}>
            Generate
          </button>
        </div>
      </div>
      {props.graph ? (
        <>
          {props.graph.assumptions.length ? (
            <Panel title="Assumptions">
              <ul className="space-y-1">
                {props.graph.assumptions.map((assumption, index) => (
                  <li key={index}>{assumption}</li>
                ))}
              </ul>
            </Panel>
          ) : null}
          <BeautifulProcessGraph graph={props.graph} />
        </>
      ) : (
        <EmptyState text="Enter a process description and generate a graph." />
      )}
    </section>
  );
}

function DataPage(props: {
  caseCount: number;
  seed: number;
  latestLog: EventLog | null;
  onCaseCount: (value: number) => void;
  onSeed: (value: number) => void;
  onGenerate: () => void;
  onDefaults: () => void;
  onUpload: (file: File | undefined) => void;
}) {
  const log = props.latestLog;
  return (
    <section className="space-y-4">
      <PageTitle title="Generate Real Data" text="Creates deterministic synthetic event logs with canonical steps, hidden workarounds, loops, delays, and risky bypass attempts." />
      <div className="panel grid gap-4 p-4 md:grid-cols-4">
        <label className="text-sm">
          Cases
          <input className="mt-1 w-full border border-neutral-300 px-3 py-2" type="number" value={props.caseCount} onChange={(event) => props.onCaseCount(Number(event.target.value))} />
        </label>
        <label className="text-sm">
          Seed
          <input className="mt-1 w-full border border-neutral-300 px-3 py-2" type="number" value={props.seed} onChange={(event) => props.onSeed(Number(event.target.value))} />
        </label>
        <button className="self-end border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onGenerate}>
          Generate
        </button>
        <button className="self-end border border-neutral-950 px-4 py-2" onClick={props.onDefaults}>
          Use demo defaults
        </button>
      </div>
      <div className="panel p-4">
        <label className="text-sm font-semibold">Upload event log CSV</label>
        <input className="mt-2 block w-full text-sm" type="file" accept=".csv" onChange={(event) => props.onUpload(event.target.files?.[0])} />
      </div>
      {log ? (
        <>
          <MetricGrid
            items={[
              ['Total cases', log.case_count],
              ['Total events', log.row_count],
              ['Hidden steps', log.hidden_step_count],
              ['Hidden case rate', String(log.metadata.hidden_case_rate ?? '')],
              ['Top hidden issue', String(log.metadata.top_hidden_issue ?? '')],
            ]}
          />
          <a className="inline-block border border-neutral-950 px-4 py-2 text-sm" href={`${API_URL}${log.download_url}`}>
            Download CSV
          </a>
          <PreviewTable rows={log.preview || []} />
        </>
      ) : (
        <EmptyState text="Generate or upload an event log." />
      )}
    </section>
  );
}

function MinePage(props: {
  processes: IdealProcess[];
  eventLogs: EventLog[];
  selectedProcessId: string;
  selectedLogId: string;
  selectedLog: EventLog | null;
  miningRun: MiningRun | null;
  onProcess: (id: string) => void;
  onLog: (id: string) => void;
  onMine: () => void;
}) {
  const valid = Boolean(props.selectedProcessId && props.selectedLogId);
  return (
    <section className="space-y-4">
      <PageTitle title="Mine Process" text="Uses PM4Py to build frequency/performance directly-follows graphs and variants, then compares them to the canonical BPM model." />
      <div className="panel grid gap-4 p-4 md:grid-cols-3">
        <label className="text-sm">
          Ideal process
          <select className="mt-1 w-full border border-neutral-300 px-3 py-2" value={props.selectedProcessId} onChange={(event) => props.onProcess(event.target.value)}>
            <option value="">Select</option>
            {props.processes.map((process) => (
              <option key={process.id} value={process.id}>
                {process.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Event log
          <select className="mt-1 w-full border border-neutral-300 px-3 py-2" value={props.selectedLogId} onChange={(event) => props.onLog(event.target.value)}>
            <option value="">Select</option>
            {props.eventLogs.map((log) => (
              <option key={log.id} value={log.id}>
                {log.filename}
              </option>
            ))}
          </select>
        </label>
        <button className="self-end border border-neutral-950 bg-neutral-950 px-4 py-2 text-white disabled:border-neutral-300 disabled:bg-neutral-200 disabled:text-neutral-500" disabled={!valid} onClick={props.onMine}>
          Mine process
        </button>
      </div>
      {props.selectedLog ? (
        <MetricGrid
          items={[
            ['Cases', props.selectedLog.case_count],
            ['Events', props.selectedLog.row_count],
            ['Date range', `${props.selectedLog.date_start ?? ''} to ${props.selectedLog.date_end ?? ''}`],
            ['Hidden steps', props.selectedLog.hidden_step_count],
          ]}
        />
      ) : null}
      {props.miningRun ? (
        <>
          <MetricGrid
            items={Object.entries(props.miningRun.metrics).map(([key, value]) => [key.replaceAll('_', ' '), String(value)] as [string, unknown])}
          />
          <GraphView nodes={props.miningRun.nodes} edges={props.miningRun.edges} mode="mined" />
          <div className="grid gap-4 lg:grid-cols-3">
            <TablePanel title="Top variants" rows={props.miningRun.top_variants} />
            <TablePanel title="Top hidden issues" rows={props.miningRun.top_hidden_issues} />
            <TablePanel title="Top bottlenecks" rows={props.miningRun.top_bottlenecks} />
          </div>
          <div className="panel p-4 text-sm text-neutral-700">
            Mined evidence: PM4Py discovered frequency and performance directly-follows graphs plus variants. The app compares PM4Py edges to the BPM model; red marks hidden or non-canonical paths, orange marks high-delay canonical bottlenecks.
          </div>
        </>
      ) : (
        <EmptyState text="Select valid inputs, then mine the process." />
      )}
    </section>
  );
}

function DocumentsPage(props: {
  title: string;
  documents: DocumentSummary[];
  selected: DocumentSummary | null;
  chunks: RagChunk[];
  onGenerate: () => void;
  onOpen: (doc: DocumentSummary) => void;
}) {
  return (
    <section className="space-y-4">
      <PageTitle title={props.title} text={props.title === 'SOPs' ? 'Governed procedures stored for retrieval.' : 'Governance thresholds, approvals, and agent boundaries stored for retrieval.'} />
      <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onGenerate}>
        Generate {props.title}
      </button>
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="panel divide-y divide-neutral-200">
          {props.documents.length ? (
            props.documents.map((doc) => (
              <button key={doc.id} className="block w-full p-3 text-left text-sm hover:bg-neutral-50" onClick={() => props.onOpen(doc)}>
                <strong>{doc.title}</strong>
                <div className="mt-1 text-xs text-neutral-500">{doc.source_repository}</div>
              </button>
            ))
          ) : (
            <EmptyState text="Generate documents first." />
          )}
        </div>
        <div className="space-y-4">
          <div className="panel min-h-[360px] p-4">
            {props.selected?.content ? (
              <>
                <div className="mb-3 border-b border-neutral-200 pb-3 text-xs text-neutral-500">{props.selected.source_file_path}</div>
                <pre className="whitespace-pre-wrap text-sm leading-6">{props.selected.content}</pre>
              </>
            ) : (
              <EmptyState text="Open a document file." />
            )}
          </div>
          <div className="panel p-4">
            <h3 className="font-semibold">Chunks and Embeddings</h3>
            <p className="mt-1 text-sm text-neutral-600">RAG chunks stored in pgvector for the selected markdown file.</p>
            <div className="mt-4 space-y-3">
              {props.chunks.length ? (
                props.chunks.map((chunk) => (
                  <div key={chunk.chunk_id} className="border border-neutral-300 p-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <strong>Chunk {chunk.chunk_index}</strong>
                      <span className="badge">{chunk.embedding_dimensions} dims</span>
                    </div>
                    <pre className="mt-2 max-h-[160px] overflow-auto whitespace-pre-wrap bg-neutral-50 p-2 text-xs">{chunk.chunk_text}</pre>
                    <div className="mt-2 text-xs text-neutral-600">embedding preview</div>
                    <pre className="mt-1 overflow-auto bg-neutral-50 p-2 text-xs">{JSON.stringify(chunk.embedding_preview, null, 2)}</pre>
                  </div>
                ))
              ) : (
                <EmptyState text="Rebuild the RAG index, then select this file again to see chunks and embeddings." />
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function RagPage(props: {
  status: Record<string, unknown>;
  query: string;
  results: Record<string, unknown>[];
  onQuery: (value: string) => void;
  onReindex: () => void;
  onSearch: () => void;
}) {
  return (
    <section className="space-y-4">
      <PageTitle title="RAG Index" text="Chunks SOPs, policies, process summaries, and mined summaries. Raw event rows are not embedded." />
      <div className="flex gap-3">
        <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onReindex}>
          Rebuild RAG index
        </button>
      </div>
      <MetricGrid items={Object.entries(props.status).map(([key, value]) => [key.replaceAll('_', ' '), JSON.stringify(value)] as [string, unknown])} />
      <div className="panel flex gap-3 p-4">
        <input className="flex-1 border border-neutral-300 px-3 py-2" value={props.query} onChange={(event) => props.onQuery(event.target.value)} />
        <button className="border border-neutral-950 px-4 py-2" onClick={props.onSearch}>
          Search
        </button>
      </div>
      <div className="space-y-3">
        {props.results.map((result) => (
          <div key={String(result.chunk_id)} className="panel p-4 text-sm">
            <div className="flex justify-between">
              <strong>{String(result.title)}</strong>
              <span className="badge">Similarity {String(result.similarity)}</span>
            </div>
            <div className="mt-2 text-neutral-600">{String(result.source_type)}</div>
            <p className="mt-3 text-neutral-800">{String(result.chunk_text).slice(0, 700)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function AiPage(props: { question: string; answer: Record<string, unknown> | null; onQuestion: (value: string) => void; onAsk: () => void; onCanned: (question: string) => void }) {
  const canned = ['Why are invoices delayed?', 'Which hidden process is most damaging?', 'What can we automate safely?', 'What controls prevent full automation?', 'Which systems need configuration changes?'];
  return (
    <section className="space-y-4">
      <PageTitle title="AI Analysis" text="AI recommendation grounded in retrieved sources, mined evidence, visible trace, assumptions, and missing information." />
      <div className="flex flex-wrap gap-2">
        {canned.map((question) => (
          <button key={question} className="border border-neutral-300 px-3 py-2 text-sm" onClick={() => props.onCanned(question)}>
            {question}
          </button>
        ))}
      </div>
      <div className="panel flex gap-3 p-4">
        <input className="flex-1 border border-neutral-300 px-3 py-2" value={props.question} onChange={(event) => props.onQuestion(event.target.value)} />
        <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onAsk}>
          Ask
        </button>
      </div>
      {props.answer ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="AI recommendation">{String(props.answer.answer)}</Panel>
          <Panel title="Mined evidence">{listText(props.answer.evidence_used)}</Panel>
          <Panel title="Visible trace">{listText(props.answer.visible_trace)}</Panel>
          <Panel title="Retrieved sources">{listText(props.answer.retrieved_sources)}</Panel>
          <Panel title="Assumptions">{listText(props.answer.assumptions)}</Panel>
          <Panel title="Missing information">{listText(props.answer.missing_information)}</Panel>
        </div>
      ) : (
        <EmptyState text="Ask a grounded process question after rebuilding the RAG index." />
      )}
    </section>
  );
}

function ImprovePage(props: {
  proposalResult: Record<string, unknown> | null;
  proposals: Proposal[];
  onGenerate: () => void;
  onApprove: (action: ImprovementAction) => void;
  onReject: (action: ImprovementAction) => void;
}) {
  return (
    <section className="space-y-4">
      <PageTitle title="Improve Process" text="Generates bounded proposals. Every action starts pending and needs human approval before agent execution." />
      <button className="border border-neutral-950 bg-neutral-950 px-4 py-2 text-white" onClick={props.onGenerate}>
        Generate improvements
      </button>
      {props.proposalResult ? <Panel title="Blocked recommendations">{listText(props.proposalResult.blocked_recommendations)}</Panel> : null}
      <div className="space-y-4">
        {props.proposals.length ? (
          props.proposals.map((proposal) => (
            <div key={proposal.id} className="panel p-4">
              <div className="flex justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">{proposal.title}</h3>
                  <p className="mt-2 text-sm text-neutral-700">{proposal.problem_statement}</p>
                </div>
                <span className={`badge ${proposal.risk_level === 'medium' ? 'badge-orange' : proposal.risk_level === 'high' ? 'badge-red' : ''}`}>{proposal.risk_level}</span>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <Panel title="Evidence">{listText(proposal.evidence)}</Panel>
                <Panel title="Expected impact">{proposal.expected_impact}</Panel>
                <Panel title="Required approvers">{proposal.required_approvers.join(', ')}</Panel>
              </div>
              <div className="mt-4 space-y-3">
                {proposal.actions.map((action) => (
                  <div key={action.id} className="border border-neutral-300 p-3 text-sm">
                    <div className="flex justify-between">
                      <strong>{action.title}</strong>
                      <span className={`badge ${action.approval_status === 'approved' ? 'badge-green' : action.approval_status === 'rejected' ? 'badge-red' : 'badge-orange'}`}>{action.approval_status}</span>
                    </div>
                    <div className="mt-1 text-neutral-600">{action.target_system} · {action.action_type}</div>
                    <p className="mt-2">{action.description}</p>
                    {action.approval_status === 'pending' ? (
                      <div className="mt-3 flex gap-2">
                        <button className="border border-neutral-950 px-3 py-1" onClick={() => props.onApprove(action)}>
                          Approve
                        </button>
                        <button className="border border-red-700 px-3 py-1 text-red-800" onClick={() => props.onReject(action)}>
                          Reject
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ))
        ) : (
          <EmptyState text="Generate proposals after mining and RAG indexing." />
        )}
      </div>
    </section>
  );
}

function AgentsPage(props: { actions: ImprovementAction[]; runs: AgentRun[]; selectedRun: AgentRun | null; onRun: (action: ImprovementAction) => void; onSelect: (run: AgentRun) => void }) {
  const steps = ['Load approved action', 'Check approval', 'Retrieve context', 'Generate config', 'Validate config', 'Store config', 'Complete'];
  return (
    <section className="space-y-4">
      <PageTitle title="Agents" text="Human approved actions can run a mock agent. No real external API is called." />
      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <div className="space-y-4">
          <div className="panel p-4">
            <h3 className="font-semibold">Ready for agent execution</h3>
            <div className="mt-3 space-y-3">
              {props.actions.length ? (
                props.actions.map((action) => (
                  <div key={action.id} className="border border-neutral-300 p-3 text-sm">
                    <strong>{action.title}</strong>
                    <div className="mt-1 text-neutral-600">{action.target_system}</div>
                    <button className="mt-3 border border-neutral-950 bg-neutral-950 px-3 py-1 text-white" onClick={() => props.onRun(action)}>
                      Run agent
                    </button>
                  </div>
                ))
              ) : (
                <EmptyState text="Approve an improvement action first." />
              )}
            </div>
          </div>
          <div className="panel p-4">
            <h3 className="font-semibold">Agent runs</h3>
            <div className="mt-3 space-y-2">
              {props.runs.map((run) => (
                <button key={run.id} className="block w-full border border-neutral-300 p-2 text-left text-sm" onClick={() => props.onSelect(run)}>
                  {run.id.slice(0, 8)} · {run.status}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="panel p-4">
            <h3 className="font-semibold">Execution trace</h3>
            <div className="mt-4 grid gap-2 md:grid-cols-7">
              {steps.map((step, index) => {
                const actual = props.selectedRun?.steps.find((item) => item.step_order === index + 1);
                return (
                  <div key={step} className={`min-h-[86px] border p-2 text-xs ${actual?.status === 'failed' ? 'border-red-700 text-red-800' : actual?.status === 'completed' ? 'border-green-700 text-green-800' : 'border-neutral-300 text-neutral-500'}`}>
                    {step}
                    <div className="mt-2">{actual?.status || 'pending'}</div>
                  </div>
                );
              })}
            </div>
          </div>
          {props.selectedRun ? (
            <>
              <JsonBlock title="Mock generated configuration" value={props.selectedRun.config_json} />
              <JsonBlock title="Validation result" value={props.selectedRun.validation_result} />
              <JsonBlock title="Audit trail" value={props.selectedRun.steps} />
            </>
          ) : (
            <EmptyState text="Run or select an agent run." />
          )}
        </div>
      </div>
    </section>
  );
}

function PageTitle({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h2 className="text-2xl font-semibold">{title}</h2>
      <p className="mt-1 max-w-4xl text-sm text-neutral-600">{text}</p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="panel p-6 text-sm text-neutral-600">{text}</div>;
}

function MetricGrid({ items }: { items: [string, unknown][] }) {
  return (
    <div className="grid gap-3 md:grid-cols-5">
      {items.map(([label, value]) => (
        <div key={label} className="panel p-3">
          <div className="text-xs uppercase text-neutral-500">{label}</div>
          <div className="mt-2 break-words text-lg font-semibold">{String(value)}</div>
        </div>
      ))}
    </div>
  );
}

function PreviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <EmptyState text="No preview rows." />;
  const columns = Object.keys(rows[0]).slice(0, 10);
  return (
    <div className="panel max-h-[480px] overflow-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="sticky top-0 bg-white">
          <tr>
            {columns.map((column) => (
              <th key={column} className="border-b border-neutral-300 px-3 py-2">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 100).map((row, index) => (
            <tr key={index} className={row.is_hidden_step ? 'bg-red-50' : ''}>
              {columns.map((column) => (
                <td key={column} className="border-b border-neutral-100 px-3 py-2">
                  {String(row[column] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TablePanel({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  return (
    <div className="panel p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3 space-y-2 text-xs">
        {rows.map((row, index) => (
          <pre key={index} className="overflow-auto border border-neutral-200 p-2">
            {JSON.stringify(row, null, 2)}
          </pre>
        ))}
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="panel p-4 text-sm">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-2 text-neutral-700">{children}</div>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="panel p-4">
      <h3 className="font-semibold">{title}</h3>
      <pre className="mt-3 max-h-[420px] overflow-auto bg-neutral-50 p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function listText(value: unknown) {
  if (Array.isArray(value)) {
    return (
      <ul className="space-y-1">
        {value.map((item, index) => (
          <li key={index}>{typeof item === 'string' ? item : JSON.stringify(item)}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '');
}
