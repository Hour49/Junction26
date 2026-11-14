import { CountryPicker } from './CountryPicker';
import { ProjectPicker } from './ProjectPicker';
import { packOf, routeHref, withPack, type Route } from './route';
import { PRODUCT_NAME } from './strings';
import logo from './vellum-logo.png';

interface ViewLink {
  label: string;
  href: string;
  current: boolean;
}

function viewLinks(route: Route): ViewLink[] {
  if (!('projectId' in route)) return [];
  const pid = route.projectId;
  const pack = packOf(route);
  const tab = (label: string, path: string, current: boolean) => ({
    label,
    href: withPack(`#/p/${pid}${path}`, pack),
    current,
  });
  // shared.md "Header tabs": Checks only with a pack (or on its own route); Surveyor only on drawing routes. No
  // Engineer tab (Tudor 12:46): the engineer route is reached from the chat's and the drawings' links.
  const links = [
    tab('Ingest', '', route.name === 'project' || route.name === 'file'),
    tab('Conflicts', '/conflicts', route.name === 'conflicts'),
    ...(pack !== null || route.name === 'checks'
      ? [tab('Checks', '/checks', route.name === 'checks')]
      : []),
    tab('Issues', '/issues', route.name === 'issues'),
    tab('Chat', '/chat', route.name === 'chat'),
  ];
  if (route.name !== 'workspace') return links;
  return [
    ...links,
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
        <ProjectPicker
          projectId={'projectId' in route ? route.projectId : null}
          pack={packOf(route)}
        />
        {'projectId' in route && <CountryPicker pack={packOf(route)} />}
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
