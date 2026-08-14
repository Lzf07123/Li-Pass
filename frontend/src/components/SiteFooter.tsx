import {
  COPYRIGHT_HOLDER,
  FOOTER_LINKS,
  ICP_FILING_ICON,
  ICP_FILING_TEXT,
  ICP_FILING_URL,
  POLICE_FILING_ICON,
  POLICE_FILING_TEXT,
  POLICE_FILING_URL,
} from "../lib/brand";

const filingLinks = (
  <>
    {ICP_FILING_TEXT && (
      <a
        href={ICP_FILING_URL}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 whitespace-nowrap transition-colors duration-200 hover:text-foreground"
      >
        <img src={ICP_FILING_ICON} alt="" className="h-3.5 w-auto" />
        {ICP_FILING_TEXT}
      </a>
    )}
    {POLICE_FILING_TEXT && (
      <a
        href={POLICE_FILING_URL}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 whitespace-nowrap transition-colors duration-200 hover:text-foreground"
      >
        <img src={POLICE_FILING_ICON} alt="" className="h-3.5 w-auto" />
        {POLICE_FILING_TEXT}
      </a>
    )}
  </>
);

export function SiteFooter({ compact = false }: { compact?: boolean }) {
  const year = new Date().getFullYear();

  if (compact) {
    return (
      <p className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>© {year} {COPYRIGHT_HOLDER}</span>
        {filingLinks}
      </p>
    );
  }

  return (
    <footer className="relative mt-auto border-t border-border/60 bg-surface/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:justify-center sm:gap-4 lg:px-8">
        <span>© {year} {COPYRIGHT_HOLDER}</span>
        {filingLinks}
        {FOOTER_LINKS.length > 0 && (
          <>
            <span className="hidden text-border sm:inline" aria-hidden="true">
              |
            </span>
            <span className="flex items-center gap-3">
              {FOOTER_LINKS.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="transition-colors duration-200 hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
            </span>
          </>
        )}
      </div>
    </footer>
  );
}
