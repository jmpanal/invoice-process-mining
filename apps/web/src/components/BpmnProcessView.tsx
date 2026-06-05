import { useEffect, useMemo, useRef, useState } from 'react';
import BpmnViewer from 'bpmn-js/lib/NavigatedViewer';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn.css';
import { ProcessEdge, ProcessNode } from '../types';

type Props = {
  nodes: ProcessNode[];
  edges: ProcessEdge[];
  variant?: 'canonical' | 'mined';
};

type Point = {
  x: number;
  y: number;
};

type Bounds = Point & {
  width: number;
  height: number;
};

const TASK_SIZE = { width: 150, height: 80 };
const EVENT_SIZE = { width: 44, height: 44 };
const GATEWAY_SIZE = { width: 60, height: 60 };

function escapeXml(value: string) {
  return value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function bpmnType(node: ProcessNode) {
  if (node.node_type === 'start') return 'bpmn:startEvent';
  if (node.node_type === 'end') return 'bpmn:endEvent';
  if (node.node_type === 'gateway') return 'bpmn:exclusiveGateway';
  return 'bpmn:task';
}

function nodeSize(node: ProcessNode) {
  if (node.node_type === 'start' || node.node_type === 'end') return EVENT_SIZE;
  if (node.node_type === 'gateway') return GATEWAY_SIZE;
  return TASK_SIZE;
}

function center(position: Point, node: ProcessNode): Point {
  const size = nodeSize(node);
  return { x: position.x + size.width / 2, y: position.y + size.height / 2 };
}

function buildLayout(nodes: ProcessNode[], edges: ProcessEdge[]) {
  const minedFixed = new Map<string, Point>([
    ['Invoice received', { x: 80, y: 270 }],
    ['Validate invoice data', { x: 220, y: 252 }],
    ['Check PO exists', { x: 430, y: 252 }],
    ['Run three-way match', { x: 640, y: 252 }],
    ['Run duplicate invoice check', { x: 870, y: 252 }],
    ['Check vendor risk', { x: 1110, y: 252 }],
    ['Check approval threshold', { x: 1350, y: 252 }],
    ['Finance manager approval', { x: 1590, y: 120 }],
    ['Auto approve for payment scheduling', { x: 1590, y: 400 }],
    ['Schedule payment', { x: 1830, y: 252 }],
    ['Send remittance notice', { x: 2050, y: 252 }],
    ['Invoice paid', { x: 2310, y: 270 }],
  ]);
  if (nodes.every((node) => minedFixed.has(node.activity || node.label || node.id))) {
    return new Map(nodes.map((node) => [node.id, minedFixed.get(node.activity || node.label || node.id) ?? { x: 80, y: 80 }]));
  }

  const fixed = new Map<string, Point>([
    ['start', { x: 80, y: 360 }],
    ['validate', { x: 210, y: 342 }],
    ['check_po', { x: 420, y: 342 }],
    ['three_way', { x: 630, y: 342 }],
    ['po_match_ok', { x: 860, y: 352 }],
    ['resolve_exception', { x: 860, y: 90 }],
    ['duplicate_check', { x: 1120, y: 342 }],
    ['duplicate_found', { x: 1370, y: 352 }],
    ['risk_threshold', { x: 1620, y: 342 }],
    ['manual_approval_required', { x: 1870, y: 352 }],
    ['approval', { x: 2110, y: 120 }],
    ['schedule_payment', { x: 2110, y: 520 }],
    ['remittance', { x: 2350, y: 520 }],
    ['end_paid', { x: 2630, y: 360 }],
    ['end_rejected', { x: 1878, y: 700 }],
  ]);
  if (nodes.every((node) => fixed.has(node.id))) return fixed;

  const outgoing = new Map(nodes.map((node) => [node.id, edges.filter((edge) => edge.source === node.id)]));
  const start = nodes.find((node) => node.node_type === 'start')?.id ?? nodes[0]?.id;
  const rank = new Map<string, number>();
  const queue: { id: string; rank: number }[] = start ? [{ id: start, rank: 0 }] : [];
  while (queue.length) {
    const next = queue.shift();
    if (!next || rank.has(next.id)) continue;
    rank.set(next.id, next.rank);
    for (const edge of outgoing.get(next.id) ?? []) queue.push({ id: edge.target || '', rank: next.rank + 1 });
  }
  for (const node of nodes) {
    if (!rank.has(node.id)) rank.set(node.id, rank.size);
  }
  const grouped = new Map<number, string[]>();
  for (const node of nodes) {
    const nodeRank = rank.get(node.id) ?? 0;
    grouped.set(nodeRank, [...(grouped.get(nodeRank) ?? []), node.id]);
  }
  return new Map(
    nodes.map((node) => {
      const nodeRank = rank.get(node.id) ?? 0;
      const row = grouped.get(nodeRank)?.indexOf(node.id) ?? 0;
      return [node.id, { x: 80 + nodeRank * 240, y: 110 + row * 150 }];
    }),
  );
}

function boundsFor(node: ProcessNode, position: Point): Bounds {
  const size = nodeSize(node);
  return { x: position.x, y: position.y, width: size.width, height: size.height };
}

function dockPoints(source: Bounds, target: Bounds): Point[] {
  const sourceCenter = { x: source.x + source.width / 2, y: source.y + source.height / 2 };
  const targetCenter = { x: target.x + target.width / 2, y: target.y + target.height / 2 };
  const leftToRight = targetCenter.x >= sourceCenter.x;
  const start = {
    x: leftToRight ? source.x + source.width : source.x,
    y: sourceCenter.y,
  };
  const end = {
    x: leftToRight ? target.x : target.x + target.width,
    y: targetCenter.y,
  };
  if (Math.abs(start.y - end.y) < 4) return [start, end];
  const midX = start.x + (end.x - start.x) / 2;
  return [start, { x: midX, y: start.y }, { x: midX, y: end.y }, end];
}

function waypointXml(points: Point[]) {
  return points.map((point) => `<di:waypoint x="${Math.round(point.x)}" y="${Math.round(point.y)}" />`).join('');
}

function manualRoute(edge: ProcessEdge, source: Bounds, target: Bounds): Point[] | null {
  const sourceId = edge.source || '';
  const targetId = edge.target || '';
  const sourceRight = { x: source.x + source.width, y: source.y + source.height / 2 };
  const sourceLeft = { x: source.x, y: source.y + source.height / 2 };
  const sourceTop = { x: source.x + source.width / 2, y: source.y };
  const sourceBottom = { x: source.x + source.width / 2, y: source.y + source.height };
  const targetLeft = { x: target.x, y: target.y + target.height / 2 };
  const targetRight = { x: target.x + target.width, y: target.y + target.height / 2 };
  const targetTop = { x: target.x + target.width / 2, y: target.y };
  const targetBottom = { x: target.x + target.width / 2, y: target.y + target.height };

  if (sourceId === 'po_match_ok' && targetId === 'resolve_exception') {
    return [sourceTop, { x: sourceTop.x, y: targetBottom.y + 34 }, { x: targetBottom.x, y: targetBottom.y + 34 }, targetBottom];
  }
  if (sourceId === 'resolve_exception' && targetId === 'duplicate_check') {
    return [sourceRight, { x: targetTop.x, y: sourceRight.y }, targetTop];
  }
  if (sourceId === 'po_match_ok' && targetId === 'duplicate_check') {
    return [sourceRight, targetLeft];
  }
  if (sourceId === 'duplicate_found' && targetId === 'end_rejected') {
    return [sourceBottom, { x: sourceBottom.x, y: targetLeft.y }, targetLeft];
  }
  if (sourceId === 'manual_approval_required' && targetId === 'approval') {
    return [sourceTop, { x: sourceTop.x, y: targetLeft.y }, targetLeft];
  }
  if (sourceId === 'manual_approval_required' && targetId === 'schedule_payment') {
    return [sourceBottom, { x: sourceBottom.x, y: targetLeft.y }, targetLeft];
  }
  if (sourceId === 'approval' && targetId === 'schedule_payment') {
    return [sourceBottom, targetTop];
  }
  if (sourceId === 'remittance' && targetId === 'end_paid') {
    return [sourceRight, { x: 2520, y: sourceRight.y }, { x: 2520, y: targetLeft.y }, targetLeft];
  }
  return null;
}

function nodeElement(node: ProcessNode, incoming: ProcessEdge[], outgoing: ProcessEdge[]) {
  const incomingXml = incoming.map((edge) => `<bpmn:incoming>${edge.id}</bpmn:incoming>`).join('');
  const outgoingXml = outgoing.map((edge) => `<bpmn:outgoing>${edge.id}</bpmn:outgoing>`).join('');
  return `<${bpmnType(node)} id="${node.id}" name="${escapeXml(node.label || node.activity || node.id)}">${incomingXml}${outgoingXml}</${bpmnType(node)}>`;
}

function safeFlowId(edge: ProcessEdge, index: number) {
  const source = edge.source || edge.source_activity || 'source';
  const target = edge.target || edge.target_activity || 'target';
  return `Flow_${index}_${source}_${target}`.replace(/[^A-Za-z0-9_]/g, '_');
}

function bpmnNodeId(node: ProcessNode, index: number) {
  return `Node_${index}_${(node.activity || node.label || node.id).replace(/[^A-Za-z0-9_]/g, '_')}`;
}

function normalizeBpmnNodes(nodes: ProcessNode[]) {
  return nodes.map((node, index) => ({ ...node, id: bpmnNodeId(node, index) }));
}

function mainMinedNodes(nodes: ProcessNode[]) {
  const main = [
    'Invoice received',
    'Validate invoice data',
    'Check PO exists',
    'Run three-way match',
    'Run duplicate invoice check',
    'Check vendor risk',
    'Check approval threshold',
    'Finance manager approval',
    'Auto approve for payment scheduling',
    'Schedule payment',
    'Send remittance notice',
    'Invoice paid',
  ];
  const byName = new Map(nodes.map((node) => [node.activity || node.label || node.id, node]));
  return main.map((name) => byName.get(name)).filter((node): node is ProcessNode => Boolean(node));
}

function mainMinedEdges(edges: ProcessEdge[]) {
  const allowed = new Set([
    'Invoice received->Validate invoice data',
    'Validate invoice data->Check PO exists',
    'Check PO exists->Run three-way match',
    'Run three-way match->Run duplicate invoice check',
    'Run duplicate invoice check->Check vendor risk',
    'Check vendor risk->Check approval threshold',
    'Check approval threshold->Finance manager approval',
    'Finance manager approval->Schedule payment',
    'Check approval threshold->Auto approve for payment scheduling',
    'Auto approve for payment scheduling->Schedule payment',
    'Schedule payment->Send remittance notice',
    'Send remittance notice->Invoice paid',
  ]);
  return edges.filter((edge) => allowed.has(`${edge.source_activity}->${edge.target_activity}`));
}

export function buildBpmnXml(nodes: ProcessNode[], edges: ProcessEdge[], variant: Props['variant'] = 'canonical') {
  const baseNodes = variant === 'mined' ? mainMinedNodes(nodes) : nodes;
  const baseEdges = variant === 'mined' ? mainMinedEdges(edges) : edges;
  const indexedNodes = variant === 'mined' ? normalizeBpmnNodes(baseNodes) : baseNodes;
  const nameToId = new Map(indexedNodes.map((node) => [node.activity || node.label || node.id, node.id]));
  const originalIdToId = new Map(baseNodes.map((node, index) => [node.id, indexedNodes[index].id]));
  const nodeById = new Map(indexedNodes.map((node) => [node.id, node]));
  const validEdges = edges
    .filter((edge) => baseEdges.includes(edge))
    .map((edge, index) => ({
      ...edge,
      id: safeFlowId(edge, index),
      source: originalIdToId.get(edge.source || '') || nameToId.get(edge.source_activity || '') || '',
      target: originalIdToId.get(edge.target || '') || nameToId.get(edge.target_activity || '') || '',
    }))
    .filter((edge) => nodeById.has(edge.source) && nodeById.has(edge.target));
  const layout = buildLayout(indexedNodes, validEdges);
  const incomingByNode = new Map(indexedNodes.map((node) => [node.id, validEdges.filter((edge) => edge.target === node.id)]));
  const outgoingByNode = new Map(indexedNodes.map((node) => [node.id, validEdges.filter((edge) => edge.source === node.id)]));
  const processElements = indexedNodes.map((node) => nodeElement(node, incomingByNode.get(node.id) ?? [], outgoingByNode.get(node.id) ?? [])).join('');
  const sequenceFlows = validEdges
    .map((edge) => `<bpmn:sequenceFlow id="${edge.id}" sourceRef="${edge.source}" targetRef="${edge.target}"${edge.label ? ` name="${escapeXml(edge.label)}"` : ''} />`)
    .join('');
  const shapes = indexedNodes
    .map((node, index) => {
      const size = nodeSize(node);
      const position = layout.get(node.id) ?? { x: 80 + index * 220, y: 80 };
      return `<bpmndi:BPMNShape id="${node.id}_di" bpmnElement="${node.id}"><dc:Bounds x="${position.x}" y="${position.y}" width="${size.width}" height="${size.height}" /></bpmndi:BPMNShape>`;
    })
    .join('');
  const edgeDi = validEdges
    .map((edge) => {
      const source = nodeById.get(edge.source);
      const target = nodeById.get(edge.target);
      if (!source || !target) return '';
      const sourceBounds = boundsFor(source, layout.get(source.id) ?? { x: 80, y: 80 });
      const targetBounds = boundsFor(target, layout.get(target.id) ?? { x: 80, y: 80 });
      const route = manualRoute(edge, sourceBounds, targetBounds) ?? dockPoints(sourceBounds, targetBounds);
      return `<bpmndi:BPMNEdge id="${edge.id}_di" bpmnElement="${edge.id}">${waypointXml(route)}</bpmndi:BPMNEdge>`;
    })
    .join('');

  return `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_InvoiceCanonical" targetNamespace="http://invoice-process-lab/bpmn">
  <bpmn:process id="CanonicalInvoiceExceptionHandlingProcess" name="Canonical Invoice Exception Handling Process" isExecutable="false">${processElements}${sequenceFlows}</bpmn:process>
  <bpmndi:BPMNDiagram id="CanonicalInvoiceExceptionHandlingDiagram">
    <bpmndi:BPMNPlane id="CanonicalInvoiceExceptionHandlingPlane" bpmnElement="CanonicalInvoiceExceptionHandlingProcess">${shapes}${edgeDi}</bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;
}

export default function BpmnProcessView({ nodes, edges, variant = 'canonical' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState('');
  const xml = useMemo(() => buildBpmnXml(nodes, edges, variant), [nodes, edges, variant]);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    const viewer = new BpmnViewer({ container: containerRef.current });
    setError('');
    void viewer
      .importXML(xml)
      .then(() => {
        if (!cancelled) viewer.get('canvas').zoom('fit-viewport');
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : String(caught));
      });
    return () => {
      cancelled = true;
      viewer.destroy();
    };
  }, [xml]);

  return (
    <div className="panel h-[620px] w-full overflow-hidden">
      {error ? <div className="p-4 text-sm text-red-800">{error}</div> : null}
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
