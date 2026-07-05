export function PRLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-sm font-medium text-status-fixed underline underline-offset-2 hover:opacity-80"
    >
      View PR ↗
    </a>
  );
}
