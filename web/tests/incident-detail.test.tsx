import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Timeline } from '@/components/incident/Timeline';
import { EvidenceList } from '@/components/incident/EvidenceList';
import { BusinessImpactPanel } from '@/components/incident/BusinessImpactPanel';

describe('incident detail components', () => {
  it('timeline shows the lead duration between change and detection', () => {
    render(<Timeline changeAt="2026-08-25T09:14:00" detectedAt="2026-08-25T09:16:00" />);
    expect(screen.getByText('2m')).toBeInTheDocument();
  });
  it('evidence list renders each engine evidence line', () => {
    render(<EvidenceList items={['country: UK -> United Kingdom', 'magnitude 0.20']} />);
    expect(screen.getByText(/United Kingdom/)).toBeInTheDocument();
    expect(screen.getByText(/magnitude 0.20/)).toBeInTheDocument();
  });
  it('business impact panel renders exposures and is empty when null', () => {
    const { rerender, container } = render(
      <BusinessImpactPanel impact={{ exposures: [{ name: 'exec_dashboard', type: 'dashboard', criticality: 'HIGH', owner: 'jane' }], maxCriticality: 'HIGH' }} />,
    );
    expect(screen.getByText('exec_dashboard')).toBeInTheDocument();
    rerender(<BusinessImpactPanel impact={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
