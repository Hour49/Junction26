import { ProjectPicker } from './ProjectPicker';
import { routeHref, type Route } from './route';
import { PRODUCT_NAME } from './strings';

interface ViewLink {
  label: string;
  href: string;
  current: boolean;
}

function viewLinks(route: Route): ViewLink[] {
  if (route.name === 'project' || route.name === 'file') {
    return [{ label: 'Ingest', href: `#/p/${route.projectId}`, current: true }];
  }
  if (route.name !== 'workspace') return [];
  const role = (r: 'engineer' | 'surveyor') => routeHref({ ...route, role: r });
  return [
    { label: 'Ingest', href: `#/p/${route.projectId}`, current: false },
    { label: 'Engineer', href: role('engineer'), current: route.role === 'engineer' },
    { label: 'Surveyor', href: role('surveyor'), current: route.role === 'surveyor' },
  ];
}

export function Header({ route }: { route: Route }) {
  const links = viewLinks(route);
  return (
    <header className="app-header">
      <a className="brand" href="#/">
        {PRODUCT_NAME}
      </a>
      <ProjectPicker projectId={'projectId' in route ? route.projectId : null} />
      {links.length > 0 && (
        <nav className="view-links" aria-label="Views">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              aria-current={link.current ? 'page' : undefined}
              className={link.current ? 'current' : undefined}
            >
              {link.label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}
