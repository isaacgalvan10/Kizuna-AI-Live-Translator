import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import BrandMark from './BrandMark';

// The guest picker and the operator login share one lockup so the two can no
// longer drift (they had already diverged 32px vs 34px). The prototype owns the
// sizes: the guest card holds the mark at 32px; the connecting screen and the
// operator login at 34px. Only the connecting screen shows no seam.

describe('the shared brand lockup', () => {
  it('renders the 絆 KIZUNA mark as a serif heading in the brand colour', () => {
    render(<BrandMark />);

    const mark = screen.getByRole('heading', { name: '絆 KIZUNA' });
    expect(mark).toHaveClass('font-serif', 'font-bold', 'text-brand');
  });

  it('holds the guest-card size by default and the 34px page size on request', () => {
    const { rerender } = render(<BrandMark />);
    expect(screen.getByRole('heading', { name: '絆 KIZUNA' })).toHaveClass('text-[32px]');

    rerender(<BrandMark size="page" />);
    expect(screen.getByRole('heading', { name: '絆 KIZUNA' })).toHaveClass('text-[34px]');
  });

  it('draws the gradient seam by default and omits it where the prototype does', () => {
    const { container, rerender } = render(<BrandMark />);

    const seam = container.querySelector('[aria-hidden="true"]');
    expect(seam).toHaveClass('bg-linear-to-r', 'from-transparent', 'via-brand/85', 'to-transparent');

    rerender(<BrandMark size="page" seam={false} />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  });
});
