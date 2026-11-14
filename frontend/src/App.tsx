import { useEffect, useRef, type ComponentType } from 'react';
import { EngineerPage } from './engineer/EngineerPage';
import { FileTraceScreen } from './ingest/FileTraceScreen';
import { HomeScreen } from './ingest/HomeScreen';
import { ProjectScreen } from './ingest/ProjectScreen';
import { Header } from './shell/Header';
import { InfoBar } from './shell/InfoBar';
import { InfoProvider } from './shell/info';
import { NotFound } from './shell/NotFound';
import { parseRoute, routePath, useHash } from './shell/route';
import './shell/shell.css';
import { SurveyorScreen } from './surveyor/SurveyorScreen';

/** The screen of each route; tests pass stubs. */
export interface Screens {
  HomeScreen: ComponentType;
  ProjectScreen: ComponentType<{ projectId: string }>;
  FileTraceScreen: ComponentType<{ projectId: string; fileId: string }>;
  EngineerPage: ComponentType<{ projectId: string; drawingId: string; query: URLSearchParams }>;
  SurveyorScreen: ComponentType<{ projectId: string; drawingId: string; query: URLSearchParams }>;
}

const builtScreens: Screens = {
  HomeScreen,
  ProjectScreen,
  FileTraceScreen,
  EngineerPage,
  SurveyorScreen,
};

export function App({ screens = builtScreens }: { screens?: Screens }) {
  const hash = useHash();
  const route = parseRoute(hash);
  const key = routePath(route);
  const main = useRef<HTMLElement>(null);
  // Focus follows a route change (a new path), not a `?q=` change within a screen.
  const shown = useRef(key);
  useEffect(() => {
    if (shown.current === key) return;
    shown.current = key;
    main.current?.focus();
    document.documentElement.scrollTop = 0;
  }, [key]);
  const { HomeScreen: Home, ProjectScreen: Project, FileTraceScreen: Trace } = screens;
  const Work =
    route.name === 'workspace' && route.role === 'surveyor'
      ? screens.SurveyorScreen
      : screens.EngineerPage;
  let body;
  switch (route.name) {
    case 'home':
      body = <Home key={key} />;
      break;
    case 'project':
      body = <Project key={key} projectId={route.projectId} />;
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
    case 'not-found':
      body = <NotFound hash={hash} />;
  }
  return (
    <InfoProvider>
      <Header route={route} />
      <InfoBar />
      <main id="main" tabIndex={-1} ref={main}>
        {body}
      </main>
    </InfoProvider>
  );
}
