import { Card } from '@/components/ui/card';

export function NotFound({ hash }: { hash: string }) {
  return (
    <div className="v-page v-page--narrow">
      <Card className="grid justify-items-start gap-2 rounded-[var(--v-radius)] border-0 p-6 shadow-[var(--v-shadow)] [overflow-wrap:anywhere] max-[720px]:p-5">
        <h1 className="m-0 text-2xl leading-tight tracking-[-0.01em]">Page not found</h1>
        <p className="m-0">Nothing at {hash || '#/'}</p>
        <a href="#/">Go to the start</a>
      </Card>
    </div>
  );
}
