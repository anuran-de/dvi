import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { layoutGraph, BlastRadiusGraph } from '@/components/incident/BlastRadiusGraph';

describe('blast radius graph', () => {
  it('lays out one node per entity in three columns, deterministically', () => {
    const g = layoutGraph(['t1'], ['a1', 'a2'], [{ name: 'e1', type: 'dashboard', criticality: 'HIGH', owner: null }]);
    expect(g.nodes).toHaveLength(4);
    expect(g.nodes.filter((n) => n.col === 0)).toHaveLength(1);
    expect(g.nodes.filter((n) => n.col === 1)).toHaveLength(2);
    expect(g.nodes.filter((n) => n.col === 2)).toHaveLength(1);
    // stable across calls
    expect(layoutGraph(['t1'], ['a1', 'a2'], [{ name: 'e1', type: 'dashboard', criticality: 'HIGH', owner: null }])).toEqual(g);
  });
  it('renders an svg with the expected node count', () => {
    const { container } = render(
      <BlastRadiusGraph targets={['t1']} affected={['a1']} exposures={[]} />,
    );
    expect(container.querySelectorAll('[data-node]')).toHaveLength(2);
  });
});
