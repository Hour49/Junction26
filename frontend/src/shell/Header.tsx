import { CountryPicker } from './CountryPicker';
import { ProjectPicker } from './ProjectPicker';
import { routeHref, type Route } from './route';
import { PRODUCT_NAME } from './strings';
import logo from './vellum-logo.png';

interface ViewLink {
  label: string;
  href: string;
  current: boolean;
}

function viewLinks(route: Route): ViewLink[] {
  if (
    route.name !== 'project' &&
    route.name !== 'file' &&
    route.name !== 'conflicts' &&
    route.name !== 'chat' &&
    route.name !== 'workspace'
  )
    return [];
  const links = [
    {
      label: 'Ingest',
      href: `#/p/${route.projectId}`,
      current: route.name === 'project' || route.name === 'file',
    },
    {
      label: 'Conflicts',
      href: `#/p/${route.projectId}/conflicts`,
      current: route.name === 'conflicts',
    },
  ];
  if (route.name !== 'workspace') return links;
  // No Engineer tab (Tudor 12:46): the engineer route is reached from the chat and drawing links; Chat takes its place.
  return [
    ...links.map((link) => ({ ...link, current: false })),
    { label: 'Chat', href: `#/p/${route.projectId}/chat`, current: false },
    {
      label: 'Surveyor',
      href: routeHref({ ...route, role: 'surveyor' }),
      current: route.role === 'surveyor',
    },
  ];
}

/** The account and workspace designs are 1280 px wide; the others 1120 px. */
export const isWide = (route: Route) => route.name === 'account' || route.name === 'workspace';

export function Header({ route }: { route: Route }) {
  const links = viewLinks(route);
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
            {links.map((link) => (
              <a key={link.label} href={link.href} aria-current={link.current ? 'page' : undefined}>
                {link.label}
              </a>
            ))}
          </nav>
        )}
        <ProjectPicker projectId={'projectId' in route ? route.projectId : null} />
        <CountryPicker />
        <a
          className="header-pill workspaces-link v-press"
          href="#/workspaces"
          aria-current={route.name === 'account' ? 'page' : undefined}
        >
          Workspaces
        </a>
      </div>
    </header>
  );
}
