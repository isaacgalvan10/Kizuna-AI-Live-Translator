export default function ErrorBanner({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-xl border border-danger-line bg-danger-soft px-4 py-3 text-sm font-bold text-danger-ink"
    >
      {message}
    </p>
  );
}
