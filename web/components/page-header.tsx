/**
 * One definition of what the top of a page looks like.
 *
 * Every route used to answer this itself, and they disagreed: the ranked list
 * was `text-2xl font-semibold`, the wall was `font-serif text-3xl`, and the
 * subtitle under each was a different size again. The serif only earns its keep
 * at display sizes, so putting it here is also what keeps it off small text.
 */
export function PageHeader({
  title,
  meta,
  children,
}: {
  title: string;
  /** The one-line answer to "what am I looking at?" — usually a count. */
  meta?: React.ReactNode;
  /** Controls that belong to the page as a whole, right-aligned. */
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 flex-wrap">
      <div className="min-w-0">
        <h1 className="page-title">{title}</h1>
        {meta && <p className="mt-1.5 text-sm text-muted-foreground">{meta}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
