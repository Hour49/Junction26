import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './index.css';
import { pathRedirect } from './shell/route';

// `/stats` as a path: the app routes by hash, so it becomes `/#/stats` before the first render.
const to = pathRedirect(window.location.pathname, window.location.hash);
if (to) window.history.replaceState(null, '', to);

const root = document.getElementById('root');
if (!root) throw new Error('index.html has no #root element');
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
