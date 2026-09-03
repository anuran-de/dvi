'use client';
import { motion, useReducedMotion } from 'framer-motion';
import type { Exposure } from '@/lib/types';
import { MOTION } from '@/components/motion/tokens';

export interface GraphNode {
  id: string;
  label: string;
  col: 0 | 1 | 2;
  row: number;
  kind: 'target' | 'asset' | 'exposure';
  criticality?: string;
}
export interface GraphEdge { from: string; to: string; }

const COL_X = [80, 340, 600];
const ROW_H = 48;
const TOP = 30;

export function layoutGraph(targets: string[], affected: string[], exposures: Exposure[]) {
  const nodes: GraphNode[] = [];
  targets.forEach((t, i) => nodes.push({ id: `t:${t}`, label: t, col: 0, row: i, kind: 'target' }));
  affected.forEach((a, i) => nodes.push({ id: `a:${a}`, label: a, col: 1, row: i, kind: 'asset' }));
  exposures.forEach((e, i) => nodes.push({ id: `e:${e.name}`, label: e.name, col: 2, row: i, kind: 'exposure', criticality: e.criticality }));

  const edges: GraphEdge[] = [];
  for (const t of targets) for (const a of affected) edges.push({ from: `t:${t}`, to: `a:${a}` });
  for (const a of affected) for (const e of exposures) edges.push({ from: `a:${a}`, to: `e:${e.name}` });
  return { nodes, edges };
}

const pos = (n: GraphNode) => ({ x: COL_X[n.col], y: TOP + n.row * ROW_H });

function nodeColor(n: GraphNode): string {
  if (n.kind !== 'exposure') return 'var(--ink)';
  switch (n.criticality) {
    case 'CRITICAL':
    case 'HIGH':
      return 'var(--sev-high)';
    case 'MEDIUM':
      return 'var(--sev-medium)';
    case 'LOW':
      return 'var(--sev-low)';
    default:
      return 'var(--ink)';
  }
}

export function BlastRadiusGraph({ targets, affected, exposures }: { targets: string[]; affected: string[]; exposures: Exposure[]; }) {
  const reduced = useReducedMotion();
  const { nodes, edges } = layoutGraph(targets, affected, exposures);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const maxRows = Math.max(targets.length, affected.length, exposures.length, 1);
  const height = TOP * 2 + (maxRows - 1) * ROW_H + 20;

  return (
    <svg role="img" aria-label="Blast radius" viewBox={`0 0 720 ${height}`} className="w-full">
      {edges.map((e, i) => {
        const a = pos(byId.get(e.from)!);
        const b = pos(byId.get(e.to)!);
        return (
          <motion.line
            key={i}
            x1={a.x + 60} y1={a.y} x2={b.x - 60} y2={b.y}
            stroke="var(--border)" strokeWidth={1}
            initial={reduced ? undefined : { pathLength: 0, opacity: 0 }}
            whileInView={reduced ? undefined : { pathLength: 1, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: MOTION.slow, ease: MOTION.easeOut }}
          />
        );
      })}
      {nodes.map((n) => {
        const p = pos(n);
        const color = nodeColor(n);
        return (
          <g key={n.id} data-node data-kind={n.kind} transform={`translate(${p.x - 60}, ${p.y - 14})`}>
            <rect width={120} height={28} rx={3} fill="var(--canvas)" stroke={color} />
            <text x={60} y={18} textAnchor="middle" className="font-mono" fontSize={10} fill="var(--ink)">
              {n.label.length > 16 ? `${n.label.slice(0, 15)}…` : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
