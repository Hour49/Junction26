import { UploadBox } from './UploadBox';
import { PAGE, TAP } from './ui';
import { cn } from '@/lib/utils';

/** Route `#/` (screen 1): start a project; earlier ones are on screen 5. */
export function HomeScreen() {
  return (
    <div className={cn('v-page items-center text-center', PAGE)}>
      <h1 className="v-hero mx-auto! mb-4!">Every answer, pointed at the drawing.</h1>
      <UploadBox />
      <p className="text-[15px]">
        <a className={TAP} href="#/workspaces">
          Earlier uploads are in Workspaces
        </a>
      </p>
    </div>
  );
}
