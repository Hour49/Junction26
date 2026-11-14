import { ExportButton } from '../export/ExportButton';
import { CountryPicker } from './CountryPicker';
import { useIssuesToAnswer } from './issueCount';
import { packOf, routePath, withPack, type Route } from './route';
import { PRODUCT_NAME } from './strings';
import logo from './vellum-logo.png';

interface ViewLink {
  label: string;
  href: string;
  current: boolean;
}

/** shared.md "Demo parity": Ingest · Chat · Documents on every project route; the screens without a tab (checks,
 * engineer, surveyor) are reached from the links other screens draw. */
function viewLinks(route: Route): ViewLink[] {
  if (!('projectId' in route)) return [];
  const pid = route.projectId;
  const pack = packOf(route);
  const tab = (label: string, path: string, current: boolean) => ({
    label,
    href: withPack(`#/p/${pid}${path}`, pack),
    current,
  });
  return [
    tab('Ingest', '', route.name === 'project' || route.name === 'file'),
    tab('Chat', '/chat', route.name === 'chat'),
    tab('Documents', '/documents', route.name === 'documents'),
  ];
}

/** The account and workspace designs are 1280 px wide; the others 1120 px. */
export const isWide = (route: Route) => route.name === 'account' || route.name === 'workspace';

export function Header({ route }: { route: Route }) {
  const links = viewLinks(route);
  // The badge asks again on every route change within the project (shared.md "Documents badge").
  const toAnswer = useIssuesToAnswer(
    'projectId' in route ? route.projectId : null,
    routePath(route),
    packOf(route),
  );
  const wide = isWide(route);
  return (
    <header className="app-header">
      <div className={wide ? 'app-header-row app-header-row--wide' : 'app-header-row'}>
        <a className="brand" href="#/">
          <img className="brand-logo" src={logo} alt="" width="44" height="44" />
          <span className="brand-name">{PRODUCT_NAME}</span>
        </a>
        {links.length > 0 && (
          <nav className="view-links v-segmented" aria-label="Views">
            {links.map((link) => {
              const badge = link.label === 'Documents' && toAnswer ? toAnswer : 0;
              return (
                <a
                  key={link.label}
                  href={link.href}
                  aria-current={link.current ? 'page' : undefined}
                  aria-label={
                    badge
                      ? `Documents, ${String(badge)} issue${badge === 1 ? '' : 's'} to answer`
                      : undefined
                  }
                >
                  {link.label}
                  {badge > 0 && (
                    <span className="tab-badge" aria-hidden="true">
                      {badge}
                    </span>
                  )}
                </a>
              );
            })}
          </nav>
        )}
        {'projectId' in route && <CountryPicker pack={packOf(route)} />}
        {'projectId' in route && (
          <ExportButton key={route.projectId} projectId={route.projectId} pack={packOf(route)} />
        )}
      </div>
    </header>
  );
}
