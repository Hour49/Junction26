import { ProjectList } from './ProjectList';
import { UploadBox } from './UploadBox';
import './ingest.css';

/** Route `#/`: start a project, or open an earlier one. */
export function HomeScreen() {
  return (
    <div className="ingest">
      <UploadBox />
      <ProjectList />
    </div>
  );
}
