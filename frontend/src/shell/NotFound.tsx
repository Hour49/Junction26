export function NotFound({ hash }: { hash: string }) {
  return (
    <div className="v-page v-page--narrow">
      <section className="not-found">
        <h2>Page not found</h2>
        <p>Nothing at {hash || '#/'}</p>
        <a href="#/">Go to the start</a>
      </section>
    </div>
  );
}
