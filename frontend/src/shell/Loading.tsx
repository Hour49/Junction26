export function Loading({ label }: { label: string }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      {label}
    </p>
  );
}
