// The 絆 KIZUNA lockup — mark plus gradient seam — shared by the guest picker
// and the operator login so the two can no longer drift (they had already
// diverged 32px vs 34px). Sizes come from the prototype: the guest card holds
// the mark at 32px; the connecting screen and the operator login use 34px. Only
// the connecting screen ships without the seam.
const MARK_SIZE = {
  card: 'text-[32px]',
  page: 'text-[34px]',
} as const;

interface BrandMarkProps {
  size?: keyof typeof MARK_SIZE;
  seam?: boolean;
}

export default function BrandMark({ size = 'card', seam = true }: BrandMarkProps) {
  return (
    <div>
      <h1 className={`font-serif ${MARK_SIZE[size]} font-bold tracking-[0.01em] text-brand`}>
        絆 KIZUNA
      </h1>
      {seam && (
        <div
          className="mx-auto mt-2.5 h-px w-16 bg-linear-to-r from-transparent via-brand/85 to-transparent"
          aria-hidden="true"
        />
      )}
    </div>
  );
}
