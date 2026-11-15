import { useEffect, useRef, type ComponentType } from 'react';
import { AccountScreen } from './account/AccountScreen';
import { ChecksScreen } from './checks/ChecksScreen';
import { EngineerPage } from './engineer/EngineerPage';
import { ProjectChat } from './engineer/ProjectChat';
import { FileTraceScreen } from './ingest/FileTraceScreen';
import { HomeScreen } from './ingest/HomeScreen';
import { DocumentsScreen } from './documents/DocumentsScreen';
import { ProjectScreen } from './ingest/ProjectScreen';
import { AboutScreen } from './shell/AboutScreen';
import { Header, isWide } from './shell/Header';
import { InfoBar } from './shell/InfoBar';
import { InfoProvider } from './shell/info';
import { NotFound } from './shell/NotFound';
import { useDocumentTitle } from './shell/title';
import { packOf, parseRoute, routeHref, routePath, useHash } from './shell/route';
import './shell/shell.css';
import { SurveyorScreen } from './surveyor/SurveyorScreen';

/** The screen of each route; tests pass stubs. */
export interface Screens {
  HomeScreen: ComponentType;
  AccountScreen: ComponentType<Record<string, never>>;
  /** `query`: the route's (the old conflicts route's `?d=&q=` focus a conflict card in the embedded list). */
  ProjectScreen: ComponentType<{ projectId: string; query?: URLSearchParams }>;
  ProjectChat: ComponentType<{ projectId: string; query: URLSearchParams }>;
  ChecksScreen: ComponentType<{ projectId: string; pack: string | null }>;
  DocumentsScreen: ComponentType<{ projectId: string; pack: string | null }>;
  FileTraceScreen: ComponentType<{ projectId: string; fileId: string }>;
  EngineerPage: ComponentType<{ projectId: string; drawingId: string; query: URLSearchParams }>;
  SurveyorScreen: ComponentType<{ projectId: string; drawingId: string; query: URLSearchParams }>;
}

const builtScreens: Screens = {
  HomeScreen,
  AccountScreen,
  ProjectScreen,
  ProjectChat,
  ChecksScreen,
  DocumentsScreen,
  FileTraceScreen,
  EngineerPage,
  SurveyorScreen,
};

export function App({ screens = builtScreens }: { screens?: Screens }) {
  const hash = useHash();
  const route = parseRoute(hash);
  const key = routePath(route);
  useDocumentTitle(route);
  const main = useRef<HTMLElement>(null);
  // Focus follows a route change (a new path), not a `?q=` change within a screen.
  const shown = useRef(key);
  useEffect(() => {
    if (shown.current === key) return;
    shown.current = key;
    main.current?.focus();
    // A DOM write inside this effect, which is what the rule asks for; the compiler misreads it here.
    // eslint-disable-next-line react-hooks/immutability
    document.documentElement.scrollTop = 0;
  }, [key]);
  const {
    HomeScreen: Home,
    AccountScreen: Account,
    ProjectScreen: Project,
    ProjectChat: Chat,
    ChecksScreen: Checks,
    DocumentsScreen: Documents,
    FileTraceScreen: Trace,
  } = screens;
  const Work =
    route.name === 'workspace' && route.role === 'surveyor'
      ? screens.SurveyorScreen
      : screens.EngineerPage;
  let body;
  switch (route.name) {
    case 'home':
      body = <Home key={key} />;
      break;
    case 'account':
      body = <Account />; // one account route: no key needed (its props type is fixed empty)
      break;
    case 'project':
      body = <Project key={key} projectId={route.projectId} query={route.query} />;
      break;
    case 'chat':
      body = <Chat key={key} projectId={route.projectId} query={route.query} />;
      break;
    case 'checks':
      body = <Checks key={key} projectId={route.projectId} pack={packOf(route)} />;
      break;
    case 'documents':
      body = <Documents key={key} projectId={route.projectId} pack={packOf(route)} />;
      break;
    case 'file':
      body = <Trace key={key} projectId={route.projectId} fileId={route.fileId} />;
      break;
    case 'workspace':
      body = (
        <Work
          key={key}
          projectId={route.projectId}
          drawingId={route.drawingId}
          query={route.query}
        />
      );
      break;
    case 'about':
      body = <AboutScreen key={routeHref(route)} projectId={route.query.get('project')} />;
      break;
    case 'not-found':
      body = <NotFound hash={hash} />;
  }
  const project = 'projectId' in route ? route.projectId : null;
  return (
    <InfoProvider>
      <button
        type="button"
        className="skip-link"
        onClick={() => {
          main.current?.focus();
        }}
      >
        Skip to content
      </button>
      <Header route={route} />
      <InfoBar wide={isWide(route)} />
      <main id="main" tabIndex={-1} ref={main}>
        {body}
      </main>
      {/* Licence credits are off every screen (Tudor, #204) and reachable here (CC BY): shared.md "Credits".
          Not on Documents (2026-11-15): the other routes keep the link. */}
      {route.name !== 'about' && route.name !== 'documents' && (
        <footer className="app-foot">
          <a href={project ? `#/about?project=${project}` : '#/about'}>About and credits</a>
        </footer>
      )}
    </InfoProvider>
  );
}
