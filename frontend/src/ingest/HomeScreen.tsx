import { UploadBox } from './UploadBox';
import './ingest.css';

/** Route `#/` (screen 1): start a project; earlier ones are on screen 5. */
export function HomeScreen() {
  return (
    <div className="v-page ingest ingest-home">
      <h1 className="v-hero">Every answer, pointed at the drawing.</h1>
      <UploadBox />
      <p className="ingest-earlier">
        <a href="#/workspaces">Earlier uploads are in Workspaces</a>
      </p>
    </div>
  );
}
