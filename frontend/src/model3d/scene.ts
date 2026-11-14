// The only module that imports three (model-3d.md "Bundle"); ModelView loads it with import('./scene').
import type { Highlight } from '../api';
import {
  Box3,
  Color,
  type BufferGeometry,
  type Material,
  DirectionalLight,
  HemisphereLight,
  Mesh,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
  type Object3D,
} from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export type Role = Highlight['role'];

/** What the highlight found: elements per role, ids not in the model, and the box around the found ones. */
export interface Shown {
  counts: Partial<Record<Role, number>>;
  missing: number;
  box: Box3 | null;
}

export interface View {
  shown: Shown;
  /** Turn the camera about the vertical axis through the target, in degrees. */
  rotate(degrees: number): void;
  /** Move the camera towards (< 1) or away from (> 1) the target. */
  zoom(factor: number): void;
  /** Back to the first framing. */
  reset(): void;
  dispose(): void;
}

const SIDE = new Vector3(1, 0.8, 1).normalize();

/** Places the camera so the whole box is in view (10% margin) from a fixed corner; returns the box's centre. */
export function frame(camera: PerspectiveCamera, box: Box3): Vector3 {
  const centre = box.getCenter(new Vector3());
  const radius = box.getSize(new Vector3()).length() / 2;
  const half = (camera.fov * Math.PI) / 360;
  const fit = Math.min(half, Math.atan(Math.tan(half) * camera.aspect));
  const distance = (radius / Math.sin(fit)) * 1.1;
  camera.position.copy(centre).addScaledVector(SIDE, distance);
  camera.near = distance / 100;
  camera.far = distance * 20;
  camera.lookAt(centre);
  camera.updateProjectionMatrix();
  return centre;
}

/** What the camera frames for a highlight: centred on the found elements, each side at least half the whole
 * model's, so the building stays visible around a single door (w3:p1 22:20). */
export function focusBox(found: Box3, whole: Box3): Box3 {
  const size = found.getSize(new Vector3()).max(whole.getSize(new Vector3()).multiplyScalar(0.5));
  return new Box3().setFromCenterAndSize(found.getCenter(new Vector3()), size);
}

/** Colours each listed element by its role (the first role of an id wins), `removed` half transparent, and dims
 * every other mesh; materials are cloned, never changed in place. Nothing found: nothing changes. */
export function highlight(
  root: Object3D,
  marks: readonly Highlight[],
  colours: Record<Role, string>,
): Shown {
  const roleOf = new Map<string, Role>();
  for (const m of marks) if (!roleOf.has(m.global_id)) roleOf.set(m.global_id, m.role);
  const found = new Map<string, Role>();
  root.traverse((o) => {
    const role = roleOf.get(o.name);
    if (role) found.set(o.name, role);
  });
  const counts: Shown['counts'] = {};
  for (const role of found.values()) counts[role] = (counts[role] ?? 0) + 1;
  const shown: Shown = { counts, missing: roleOf.size - found.size, box: null };
  if (found.size === 0) return shown;
  // a GLB node is named by its GlobalId; its mesh may be the node or a child of it
  const roleAbove = (o: Object3D | null): Role | undefined => {
    for (let n = o; n; n = n.parent) {
      const role = found.get(n.name);
      if (role) return role;
    }
    return undefined;
  };
  const box = new Box3();
  root.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    const mesh = o as Mesh;
    const role = roleAbove(o);
    const paint = (m: Material) => {
      const c = m.clone();
      if (role && 'color' in c && c.color instanceof Color) c.color.set(colours[role]);
      if (!role || role === 'removed') {
        c.transparent = true;
        c.opacity = role ? 0.5 : 0.12;
        c.depthWrite = !!role; // a dimmed mesh never hides what is behind it
      }
      return c;
    };
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(paint) : paint(mesh.material);
    if (role) box.expandByObject(o);
  });
  shown.box = box;
  return shown;
}

/** Draws the GLB on the canvas, sized to the canvas's parent, rendering only when something changes. */
export async function mount(
  canvas: HTMLCanvasElement,
  glb: ArrayBuffer,
  marks: readonly Highlight[] = [],
): Promise<View> {
  let root: Object3D;
  try {
    root = (await new GLTFLoader().parseAsync(glb, '')).scene;
  } catch {
    throw new Error('the model file could not be read');
  }
  const whole = new Box3().setFromObject(root);
  if (whole.isEmpty()) throw new Error('the model has no geometry');
  const style = getComputedStyle(canvas);
  const colour = (role: Role) => style.getPropertyValue(`--v-3d-${role}`).trim() || 'orange';
  const shown = highlight(root, marks, {
    moved: colour('moved'),
    removed: colour('removed'),
    added: colour('added'),
    affected: colour('affected'),
  });
  const box = shown.box ? focusBox(shown.box, whole) : whole;
  let renderer: WebGLRenderer;
  try {
    renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch {
    throw new Error('this browser cannot draw 3D');
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const sun = new DirectionalLight(0xffffff, 2);
  sun.position.set(1, 2, 1.5);
  const scene = new Scene().add(root, new HemisphereLight(0xffffff, 0x8a8a8a, 2), sun);
  const camera = new PerspectiveCamera(45, 1);
  const controls = new OrbitControls(camera, canvas);
  const render = () => {
    renderer.render(scene, camera);
  };
  const home = () => {
    controls.target.copy(frame(camera, box));
    controls.maxDistance = camera.position.distanceTo(controls.target) * 10;
    controls.update();
    render();
  };
  const move = (change: (offset: Vector3) => void) => {
    const offset = camera.position.clone().sub(controls.target);
    change(offset);
    offset.clampLength(controls.minDistance, controls.maxDistance);
    camera.position.copy(controls.target).add(offset);
    controls.update();
    render();
  };
  const host = canvas.parentElement ?? canvas;
  const resize = () => {
    const { clientWidth: w, clientHeight: h } = host;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  controls.addEventListener('change', render);
  controls.listenToKeyEvents(canvas); // arrow keys pan
  resize();
  home();
  return {
    shown,
    rotate: (degrees) => {
      move((o) => o.applyAxisAngle(camera.up, (degrees * Math.PI) / 180));
    },
    zoom: (factor) => {
      move((o) => o.multiplyScalar(factor));
    },
    reset: home,
    dispose: () => {
      observer.disconnect();
      controls.dispose();
      // shortcut: textures are not disposed; IFC GLBs carry colours only. Dispose maps if a GLB ever has them.
      root.traverse((o) => {
        if (!(o instanceof Mesh)) return;
        const mesh = o as Mesh<BufferGeometry, Material>;
        mesh.geometry.dispose();
        for (const m of [mesh.material].flat()) m.dispose();
      });
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}
