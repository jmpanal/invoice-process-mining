import dagre from '@dagrejs/dagre';
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import ReactFlow, {
  applyNodeChanges,
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeChange,
  type NodeProps,
  type ReactFlowInstance,
} from 'reactflow';
import { ProcessEdge, ProcessNode } from '../types';

type Props = {
  nodes: ProcessNode[];
  edges: ProcessEdge[];
  mode: 'bpm' | 'mined';
};

type Density = 'readable' | 'exceptions' | 'full';
type ProcessStatus = 'normal' | 'exception' | 'bottleneck';

type ProcessNodeData = {
  item: ProcessNode;
  label: string;
  kind: string;
  countLabel: string;
  percentLabel: string;
  status: ProcessStatus;
};

type ProcessEdgeData = {
  status: ProcessStatus;
  countLabel: string;
};

type ProcessFlowNode = Node<ProcessNodeData>;
type ProcessFlowEdge = Edge<ProcessEdgeData>;

const STORAGE_KEY = 'process-map-reactflow-layout:v5';
const GRID_SIZE = 16;
const NODE_WIDTH = 168;
const NODE_HEIGHT = 154;
const MAIN_X_START = 96;
const MAIN_Y = 96;
const X_GAP = 236;
const LANE_Y_GAP = 172;
const EDGE_PADDING_BOTTOM = 130;
const EDGE_PADDING_X = 40;
const EDGE_BORDER_RADIUS = 16;
const HANDLE_SIZE = 20;

const mainActivities = [
  'Invoice received',
  'Validate invoice data',
  'Check PO exists',
  'Run three-way match',
  'Run duplicate invoice check',
  'Check vendor risk',
  'Check approval threshold',
  'Finance manager approval',
  'Schedule payment',
  'Send remittance notice',
  'Invoice paid',
];

const exceptionActivityLayout: Array<[string, number, number]> = [
  ['Manual Email Review', 1, 1],
  ['Create missing PO exception', 2, 1],
  ['AP review missing PO', 2, 2],
  ['Procurement correction', 3, 2],
  ['Classify exception', 3, 1],
  ['Create price mismatch ticket', 4, 2],
  ['AP review price mismatch', 5, 2],
  ['Correction for price mismatch', 6, 2],
  ['Block invoice', 5, 1],
  ['Finance controller review', 6, 3],
  ['Invoice rejected', 7, 3],
  ['Auto approve for payment scheduling', 7, 1],
  ['Compliance review', 6, 1],
  ['Create quantity mismatch ticket', 8, 2],
  ['AP review quantity mismatch', 9, 2],
  ['Correction for quantity mismatch', 10, 2],
  ['Request goods receipt confirmation', 9, 1],
  ['Excel Price Correction', 10, 3],
  ['Ticket Reopened', 11, 1],
  ['Payment Block Bypass Attempt', 12, 1],
];

const readableExceptions = new Set<string>();

function activity(node: ProcessNode) {
  return node.activity || node.label || node.id;
}

function processStatus(node: ProcessNode): ProcessStatus {
  if (node.is_hidden || node.severity === 'hidden') return 'exception';
  if (node.is_bottleneck || node.severity === 'bottleneck') return 'bottleneck';
  return 'normal';
}

function edgeStatus(edge: ProcessEdge): ProcessStatus {
  if (edge.is_hidden || edge.severity === 'hidden') return 'exception';
  if (edge.is_bottleneck || edge.severity === 'bottleneck') return 'bottleneck';
  return 'normal';
}

function nodeKind(node: ProcessNode) {
  const status = processStatus(node);
  if (status === 'exception') return 'Exception route';
  if (status === 'bottleneck') return 'Bottleneck';
  return 'Process step';
}

function percentLabel(node: ProcessNode, maxFrequency: number) {
  if (!node.frequency || !maxFrequency) return 'n/a';
  return `${Math.round((node.frequency / maxFrequency) * 100)}%`;
}

function chipLabel(status: ProcessStatus) {
  if (status === 'exception') return 'Exception';
  if (status === 'bottleneck') return 'Delay';
  return 'Normal';
}

function nodeInitials(label: string, status: ProcessStatus) {
  if (status === 'exception') return '!';
  if (status === 'bottleneck') return 'D';

  const words = label.match(/[a-z0-9]+/gi) ?? [];
  const initials = words
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();

  return initials || '?';
}

function ProcessMapNode({ data, selected }: NodeProps<ProcessNodeData>) {
  const classes = [
    'process-flow-node',
    `process-flow-node--${data.status}`,
    selected ? 'process-flow-node--selected' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      <Handle
        id="target-left"
        type="target"
        position={Position.Left}
        className="process-flow-handle process-flow-handle--target"
      />
      <Handle
        id="source-right"
        type="source"
        position={Position.Right}
        className="process-flow-handle process-flow-handle--source"
      />
      <div className="process-flow-tile" aria-label={`${data.label}: ${data.kind}`}>
        <span className="process-flow-icon" aria-hidden="true">
          {nodeInitials(data.label, data.status)}
        </span>
        <span className="process-flow-status" aria-hidden="true" />
      </div>
      <div className="process-flow-node-label">
        <strong>{data.label}</strong>
        <span>{data.kind}</span>
      </div>
      <div className="process-flow-node-details" role="tooltip">
        <span>{data.countLabel}</span>
        <span>{data.percentLabel} of max volume</span>
        <em>{chipLabel(data.status)}</em>
      </div>
    </div>
  );
}

function isRightOfSourceHandle(sourceX: number, targetX: number) {
  return sourceX - HANDLE_SIZE > targetX;
}

function getEdgeSegments(props: EdgeProps<ProcessEdgeData>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition } = props;

  if (!isRightOfSourceHandle(sourceX, targetX)) {
    const segment = getBezierPath(props);
    return {
      segments: [segment],
      labelPosition: [segment[1], segment[2]],
      straight: sourceY === targetY,
    };
  }

  const firstSegmentTargetX = (sourceX + targetX) / 2;
  const firstSegmentTargetY = sourceY + EDGE_PADDING_BOTTOM;
  const firstSegment = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX: firstSegmentTargetX,
    targetY: firstSegmentTargetY,
    sourcePosition,
    targetPosition: Position.Right,
    borderRadius: EDGE_BORDER_RADIUS,
    offset: EDGE_PADDING_X,
  });
  const secondSegment = getSmoothStepPath({
    sourceX: firstSegmentTargetX,
    sourceY: firstSegmentTargetY,
    targetX,
    targetY,
    sourcePosition: Position.Left,
    targetPosition,
    borderRadius: EDGE_BORDER_RADIUS,
    offset: EDGE_PADDING_X,
  });

  return {
    segments: [firstSegment, secondSegment],
    labelPosition: [firstSegmentTargetX, firstSegmentTargetY],
    straight: sourceY === targetY,
  };
}

function edgeColor(status: ProcessStatus) {
  if (status === 'exception') return '#e45649';
  if (status === 'bottleneck') return '#f59e0b';
  return '#7b8494';
}

function ProcessMapEdge(props: EdgeProps<ProcessEdgeData>) {
  const status = props.data?.status ?? 'normal';
  const color = edgeColor(status);
  const { segments, labelPosition, straight } = getEdgeSegments(props);
  const edgeStyle: CSSProperties = {
    ...props.style,
    stroke: color,
    strokeWidth: status === 'normal' ? 2 : 2.5,
    strokeDasharray: status === 'exception' ? '5 6' : undefined,
    strokeLinecap: 'square',
    transition: 'stroke 0.16s ease, stroke-width 0.16s ease',
  };

  return (
    <>
      <g className={`process-flow-edge process-flow-edge--${status}`}>
        {segments.map((segment, index) => (
          <BaseEdge
            key={`${props.id}-${index}`}
            id={`${props.id}-${index}`}
            path={segment[0]}
            markerEnd={props.markerEnd}
            interactionWidth={40}
            style={edgeStyle}
          />
        ))}
      </g>
      <EdgeLabelRenderer>
        <div
          className={`process-flow-edge-label${straight ? ' process-flow-edge-label--straight' : ''}`}
          style={{
            transform: `translate(-50%, -50%) translate(${labelPosition[0]}px, ${labelPosition[1]}px)`,
          }}
        >
          {props.data?.countLabel}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes = { processNode: ProcessMapNode };
const edgeTypes = { n8nProcessEdge: ProcessMapEdge };

function edgeKey(edge: ProcessEdge) {
  return `${edge.source_activity || edge.source}->${edge.target_activity || edge.target}`;
}

function isMainEdge(edge: ProcessEdge) {
  const source = edge.source_activity || edge.source || '';
  const target = edge.target_activity || edge.target || '';
  const sourceIndex = mainActivities.indexOf(source);
  return sourceIndex >= 0 && mainActivities[sourceIndex + 1] === target;
}

function visibleEdges(edges: ProcessEdge[], density: Density) {
  if (density === 'full') return edges;
  if (density === 'exceptions') {
    return edges.filter(
      (edge) =>
        isMainEdge(edge) ||
        edge.is_hidden ||
        edge.severity === 'hidden' ||
        edge.is_bottleneck ||
        edge.severity === 'bottleneck',
    );
  }
  return edges.filter((edge) => {
    if (isMainEdge(edge)) return true;
    const source = edge.source_activity || '';
    const target = edge.target_activity || '';
    return readableExceptions.has(source) || readableExceptions.has(target);
  });
}

function buildPositions(nodes: ProcessNode[]) {
  const byActivity = new Map(nodes.map((node) => [activity(node), node]));
  const positions = new Map<string, { x: number; y: number }>();

  mainActivities.forEach((name, index) => {
    const node = byActivity.get(name);
    if (node) positions.set(node.id, { x: MAIN_X_START + index * X_GAP, y: MAIN_Y });
  });

  exceptionActivityLayout.forEach(([name, rank, lane]) => {
    const node = byActivity.get(name);
    if (node) {
      positions.set(node.id, { x: MAIN_X_START + rank * X_GAP, y: MAIN_Y + lane * LANE_Y_GAP });
    }
  });

  nodes.forEach((node, index) => {
    if (!positions.has(node.id)) {
      positions.set(node.id, {
        x: MAIN_X_START + (index % 8) * X_GAP,
        y: MAIN_Y + (3 + Math.floor(index / 8)) * LANE_Y_GAP,
      });
    }
  });

  return positions;
}

function refreshEdgeHandles(flowEdges: ProcessFlowEdge[]) {
  return flowEdges.map((edge) => ({
    ...edge,
    sourceHandle: 'source-right',
    targetHandle: 'target-left',
  }));
}

function loadSavedPositions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, { x: number; y: number }>) : {};
  } catch {
    return {};
  }
}

function snapToGrid(value: number) {
  return Math.round(value / GRID_SIZE) * GRID_SIZE;
}

function layoutWithDagre(nodes: ProcessFlowNode[], edges: ProcessFlowEdge[]) {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: 'LR',
    ranksep: GRID_SIZE * 8,
    nodesep: GRID_SIZE * 5,
    edgesep: GRID_SIZE * 2,
    marginx: GRID_SIZE * 3,
    marginy: GRID_SIZE * 3,
  });

  nodes.forEach((node) => {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  edges.forEach((edge) => {
    graph.setEdge(edge.source, edge.target);
  });

  dagre.layout(graph);

  return nodes.map((node) => {
    const dagreNode = graph.node(node.id);
    if (!dagreNode) return node;

    return {
      ...node,
      position: {
        x: snapToGrid(dagreNode.x - NODE_WIDTH / 2),
        y: snapToGrid(dagreNode.y - NODE_HEIGHT / 2),
      },
    };
  });
}

export default function GraphView({ nodes, edges }: Props) {
  const [density, setDensity] = useState<Density>('readable');
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [flowNodes, setFlowNodes] = useState<ProcessFlowNode[]>([]);
  const [flowEdges, setFlowEdges] = useState<ProcessFlowEdge[]>([]);
  const flowRef = useRef<ReactFlowInstance<ProcessNodeData, ProcessEdgeData> | null>(null);
  const nodeTypesRef = useRef(nodeTypes);
  const edgeTypesRef = useRef(edgeTypes);

  const graph = useMemo(() => {
    const filteredEdges = visibleEdges(edges, density);
    const visibleActivities = new Set<string>();
    filteredEdges.forEach((edge) => {
      if (edge.source_activity) visibleActivities.add(edge.source_activity);
      if (edge.target_activity) visibleActivities.add(edge.target_activity);
    });
    mainActivities.forEach((name) => visibleActivities.add(name));
    const visibleNodes = nodes.filter((node) => visibleActivities.has(activity(node)));
    const maxFrequency = Math.max(...nodes.map((node) => node.frequency || 0), 1);
    const positions = buildPositions(visibleNodes);
    const saved = loadSavedPositions();
    const nodeIdByActivity = new Map(visibleNodes.map((node) => [activity(node), node.id]));
    const flowNodes: ProcessFlowNode[] = visibleNodes.map((node) => {
      const status = processStatus(node);
      return {
        id: node.id,
        type: 'processNode',
        position: saved[node.id] || positions.get(node.id) || { x: 0, y: 0 },
        data: {
          item: node,
          label: activity(node),
          kind: nodeKind(node),
          countLabel: node.frequency ? `${node.frequency.toLocaleString()} cases` : 'Not measured',
          percentLabel: percentLabel(node, maxFrequency),
          status,
        },
      };
    });
    const flowEdges: ProcessFlowEdge[] = [];
    filteredEdges.forEach((edge, index) => {
      const source = nodeIdByActivity.get(edge.source_activity || '');
      const target = nodeIdByActivity.get(edge.target_activity || '');
      if (!source || !target) return;

      const status = edgeStatus(edge);
      const color = edgeColor(status);
      flowEdges.push({
        id: edge.id || `${edgeKey(edge)}-${index}`,
        source,
        target,
        sourceHandle: 'source-right',
        targetHandle: 'target-left',
        type: 'n8nProcessEdge',
        markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color },
        data: {
          status,
          countLabel: `${edge.frequency?.toLocaleString() ?? 'n/a'} cases`,
        },
      });
    });

    return { flowNodes, flowEdges };
  }, [density, edges, layoutVersion, nodes]);

  useEffect(() => {
    setFlowNodes(graph.flowNodes);
    setFlowEdges(refreshEdgeHandles(graph.flowEdges));
    fitToViewSoon();
  }, [graph]);

  function savePositions(nextNodes: ProcessFlowNode[]) {
    const positions = Object.fromEntries(nextNodes.map((node) => [node.id, node.position]));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
  }

  function fitToView() {
    flowRef.current?.fitView({ padding: 0.12, duration: 180 });
  }

  function fitToViewSoon() {
    window.requestAnimationFrame(() => fitToView());
  }

  function onNodesChange(changes: NodeChange[]) {
    setFlowNodes((current) => {
      const next = applyNodeChanges(changes, current) as ProcessFlowNode[];
      savePositions(next);
      return next;
    });
  }

  function tidyUp() {
    const nextNodes = layoutWithDagre(flowNodes, flowEdges);
    setFlowNodes(nextNodes);
    setFlowEdges(refreshEdgeHandles(flowEdges));
    savePositions(nextNodes);
    fitToViewSoon();
  }

  function resetLayout() {
    localStorage.removeItem(STORAGE_KEY);
    setDensity('readable');
    setLayoutVersion((current) => current + 1);
    fitToViewSoon();
  }

  return (
    <div className="process-map-flow-shell">
      <div className="process-map-toolbar">
        {(['readable', 'exceptions', 'full'] as Density[]).map((mode) => (
          <button key={mode} type="button" className={density === mode ? 'active' : ''} onClick={() => setDensity(mode)}>
            {mode}
          </button>
        ))}
        <span className="process-map-toolbar-spacer" />
        <button type="button" onClick={tidyUp}>
          Tidy up
        </button>
        <button type="button" onClick={fitToView}>
          Zoom to fit
        </button>
        <button type="button" onClick={resetLayout}>
          Reset layout
        </button>
      </div>
      <div className="process-map-flow-stage">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypesRef.current}
          edgeTypes={edgeTypesRef.current}
          onInit={(instance) => {
            flowRef.current = instance;
          }}
          onNodesChange={onNodesChange}
          defaultViewport={{ x: 80, y: 40, zoom: 0.72 }}
          minZoom={0.12}
          maxZoom={2}
          nodesDraggable
          snapToGrid
          snapGrid={[GRID_SIZE, GRID_SIZE]}
          fitView
          fitViewOptions={{ padding: 0.1 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={GRID_SIZE} size={1.1} color="var(--process-flow-dot)" />
          <Controls showInteractive={false} position="bottom-left" />
          <MiniMap pannable zoomable position="top-right" />
        </ReactFlow>
      </div>
    </div>
  );
}
