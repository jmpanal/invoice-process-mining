import type { CSSProperties } from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  GitBranch,
  Hand,
  Play,
  Server,
  SquareCheck,
  UserCheck,
  type LucideIcon,
} from 'lucide-react';
import ReactFlow, { applyNodeChanges, Background, Controls, Edge, Handle, MarkerType, MiniMap, Node, NodeChange, NodeProps, Position, ReactFlowInstance } from 'reactflow';
import { CustomProcessGraph, CustomGraphNode } from '../types';

type Props = {
  graph: CustomProcessGraph;
};

type NodeData = {
  item: CustomGraphNode;
};

const kindIcons: Record<string, LucideIcon> = {
  trigger: Play,
  action: SquareCheck,
  decision: GitBranch,
  wait: Clock,
  approval: UserCheck,
  system: Server,
  error: AlertTriangle,
  manual: Hand,
  data: Database,
  terminal: CheckCircle2,
};

const laneY: Record<string, number> = {
  approval: 40,
  system: 190,
  main: 340,
  exception: 520,
};

const legendItems = [
  { kind: 'trigger', label: 'Trigger', text: 'Starts the workflow.' },
  { kind: 'action', label: 'Action', text: 'Standard work step.' },
  { kind: 'decision', label: 'Decision', text: 'Branches the flow.' },
  { kind: 'approval', label: 'Approval', text: 'Human review point.' },
  { kind: 'system', label: 'System/Data', text: 'Automated or data step.' },
  { kind: 'error', label: 'Error', text: 'Failure or rejected path.' },
  { kind: 'terminal', label: 'Terminal', text: 'Process outcome.' },
];

function nodeAccent(kind: string) {
  if (kind === 'error') return '#ef4444';
  if (kind === 'approval' || kind === 'manual' || kind === 'wait') return '#f59e0b';
  if (kind === 'terminal') return '#10b981';
  if (kind === 'decision') return '#8b5cf6';
  if (kind === 'system' || kind === 'data') return '#0ea5e9';
  return '#2563eb';
}

function nodeStyle(kind: string) {
  if (kind === 'error') return 'beautiful-node--error';
  if (kind === 'approval' || kind === 'manual' || kind === 'wait') return 'beautiful-node--warning';
  if (kind === 'terminal') return 'beautiful-node--success';
  return 'beautiful-node--normal';
}

function BeautifulNode({ data, selected }: NodeProps<NodeData>) {
  const Icon = kindIcons[data.item.kind] || SquareCheck;
  const accent = nodeAccent(data.item.kind);
  return (
    <div className={`beautiful-node ${nodeStyle(data.item.kind)}${selected ? ' beautiful-node--selected' : ''}`} title={data.item.description}>
      <Handle id="target-left" type="target" position={Position.Left} className="beautiful-handle" />
      <Handle id="source-right" type="source" position={Position.Right} className="beautiful-handle" />
      <Handle id="source-left" type="source" position={Position.Left} className="beautiful-handle" />
      <Handle id="target-right" type="target" position={Position.Right} className="beautiful-handle" />
      <Handle id="target-top" type="target" position={Position.Top} className="beautiful-handle" />
      <Handle id="source-bottom" type="source" position={Position.Bottom} className="beautiful-handle" />
      <Handle id="source-top" type="source" position={Position.Top} className="beautiful-handle" />
      <Handle id="target-bottom" type="target" position={Position.Bottom} className="beautiful-handle" />
      <div className="beautiful-node-tile" style={{ '--accent': accent } as CSSProperties}>
        <Icon aria-hidden="true" size={42} strokeWidth={1.9} />
      </div>
      <div className="beautiful-node-label">{data.item.title}</div>
    </div>
  );
}

const nodeTypes = { beautifulNode: BeautifulNode };

function layoutNodes(graph: CustomProcessGraph) {
  const laneCounts = new Map<string, number>();
  const positionById = new Map<string, { x: number; y: number }>();
  graph.nodes.forEach((node, index) => {
    const lane = laneY[node.lane] === undefined ? 'main' : node.lane;
    const laneIndex = laneCounts.get(lane) || 0;
    laneCounts.set(lane, laneIndex + 1);
    positionById.set(node.id, {
      x: 90 + Math.max(index, laneIndex) * 240,
      y: laneY[lane],
    });
  });
  return positionById;
}

function handlePair(source?: { x: number; y: number }, target?: { x: number; y: number }) {
  if (!source || !target) return { sourceHandle: 'source-right', targetHandle: 'target-left' };
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? { sourceHandle: 'source-right', targetHandle: 'target-left' } : { sourceHandle: 'source-left', targetHandle: 'target-right' };
  }
  return dy >= 0 ? { sourceHandle: 'source-bottom', targetHandle: 'target-top' } : { sourceHandle: 'source-top', targetHandle: 'target-bottom' };
}

function edgeColor(type: string) {
  if (type === 'error' || type === 'rejected' || type === 'hidden') return '#ef4444';
  if (type === 'approval' || type === 'wait' || type === 'retry') return '#f59e0b';
  if (type === 'inferred') return '#8b5cf6';
  return '#64748b';
}

export default function BeautifulProcessGraph({ graph }: Props) {
  const [version, setVersion] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState(graph.nodes[0]?.id || '');
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance<NodeData, Edge> | null>(null);
  const initialFlow = useMemo(() => {
    const positions = layoutNodes(graph);
    const nodes: Node<NodeData>[] = graph.nodes.map((node) => ({
      id: node.id,
      type: 'beautifulNode',
      position: positions.get(node.id) || { x: 0, y: 0 },
      data: { item: node },
    }));
    const byId = new Map(nodes.map((node) => [node.id, node.position]));
    const edges: Edge[] = graph.edges.map((edge) => {
      const color = edgeColor(edge.type);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label || undefined,
        ...handlePair(byId.get(edge.source), byId.get(edge.target)),
        markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color },
        style: { stroke: color, strokeWidth: 2, strokeDasharray: edge.type === 'retry' || edge.type === 'inferred' ? '4 7' : undefined },
        labelStyle: { fill: color, fontWeight: 800, fontSize: 12 },
        labelBgStyle: { fill: '#ffffff', stroke: '#dbe4f0' },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 8,
      };
    });
    return { nodes, edges };
  }, [graph, version]);
  const [nodes, setNodes] = useState<Node<NodeData>[]>(initialFlow.nodes);
  const [edges, setEdges] = useState<Edge[]>(initialFlow.edges);

  useEffect(() => {
    setNodes(initialFlow.nodes);
    setEdges(initialFlow.edges);
    setSelectedNodeId(graph.nodes[0]?.id || '');
  }, [initialFlow]);

  function onNodesChange(changes: NodeChange[]) {
    setNodes((current) => applyNodeChanges(changes, current) as Node<NodeData>[]);
  }

  function fitGraph() {
    flowInstance?.fitView({ padding: 0.18, duration: 250 });
  }

  function tidyGraph() {
    setVersion((current) => current + 1);
    window.setTimeout(() => fitGraph(), 0);
  }

  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) || graph.nodes[0];

  return (
    <div className="beautiful-graph-shell">
      <div className="beautiful-graph-toolbar">
        <div>
          <strong>{graph.title}</strong>
          <span>{graph.summary}</span>
        </div>
        <div className="beautiful-graph-actions">
          <button onClick={() => flowInstance?.zoomIn({ duration: 180 })}>Zoom in</button>
          <button onClick={() => flowInstance?.zoomOut({ duration: 180 })}>Zoom out</button>
          <button onClick={fitGraph}>Fit</button>
          <button onClick={tidyGraph}>Tidy</button>
        </div>
      </div>
      <div className="beautiful-graph-stage">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onInit={setFlowInstance}
          onNodesChange={onNodesChange}
          onNodeClick={(_, node) => setSelectedNodeId(node.id)}
          nodesDraggable
          snapToGrid
          snapGrid={[20, 20]}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          minZoom={0.2}
          maxZoom={1.6}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#dbe4f0" gap={24} size={1.2} />
          <Controls position="bottom-left" showInteractive={false} />
          <MiniMap pannable zoomable position="top-right" />
        </ReactFlow>
      </div>
      <div className="beautiful-graph-footer">
        <div className="beautiful-graph-legend">
          <h3>Legend</h3>
          <div className="beautiful-legend-grid">
            {legendItems.map((item) => {
              const Icon = kindIcons[item.kind] || SquareCheck;
              return (
                <div key={item.kind} className="beautiful-legend-item">
                  <span style={{ '--accent': nodeAccent(item.kind) } as CSSProperties}>
                    <Icon size={18} strokeWidth={2} />
                  </span>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{item.text}</small>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="beautiful-node-inspector">
          <h3>Box Explanation</h3>
          {selectedNode ? (
            <>
              <strong>{selectedNode.title}</strong>
              <dl>
                <div>
                  <dt>Type</dt>
                  <dd>{selectedNode.kind}</dd>
                </div>
                <div>
                  <dt>Lane</dt>
                  <dd>{selectedNode.lane}</dd>
                </div>
              </dl>
              <p>{selectedNode.description || 'No additional detail provided.'}</p>
            </>
          ) : (
            <p>Select a box to see what it means.</p>
          )}
        </div>
      </div>
    </div>
  );
}
