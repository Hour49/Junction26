// The only module that imports three (model-3d.md "Bundle"); ModelView loads it with import('./scene').
import {
  Box3,
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

export interface View {
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

/** Draws the GLB on the canvas, sized to the canvas's parent, rendering only when something changes. */
export async function mount(canvas: HTMLCanvasElement, glb: ArrayBuffer): Promise<View> {
  let root: Object3D;
  try {
    root = (await new GLTFLoader().parseAsync(glb, '')).scene;
  } catch {
    throw new Error('the model file could not be read');
  }
  const box = new Box3().setFromObject(root);
  if (box.isEmpty()) throw new Error('the model has no geometry');
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
