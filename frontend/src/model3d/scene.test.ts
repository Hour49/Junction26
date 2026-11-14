import {
  Box3,
  BoxGeometry,
  Frustum,
  Group,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Vector3,
  type Object3D,
} from 'three';
import { describe, expect, it } from 'vitest';
import { focusBox, frame, highlight } from './scene';

describe('scene', () => {
  it('M3-14 frame puts the whole box in view with the target at its centre', () => {
    const box = new Box3(new Vector3(-10, 0, -4), new Vector3(30, 9, 6));
    const camera = new PerspectiveCamera(45, 16 / 9);
    const target = frame(camera, box);
    expect(target.toArray()).toEqual(box.getCenter(new Vector3()).toArray());
    camera.updateMatrixWorld();
    const f = new Frustum().setFromProjectionMatrix(
      new Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse),
    );
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z])
          expect(f.containsPoint(new Vector3(x, y, z))).toBe(true);
    // narrow window: still all in view (the frame fits the smaller of the two fields of view)
    const tall = new PerspectiveCamera(45, 0.4);
    frame(tall, box);
    tall.updateMatrixWorld();
    const g = new Frustum().setFromProjectionMatrix(
      new Matrix4().multiplyMatrices(tall.projectionMatrix, tall.matrixWorldInverse),
    );
    expect(g.containsPoint(box.max)).toBe(true);
    expect(g.containsPoint(box.min)).toBe(true);
  });
});

describe('highlight', () => {
  const COLOURS = { moved: '#0000ff', removed: '#ff0000', added: '#00ff00', affected: '#ff8800' };
  function house() {
    const root = new Group();
    const shared = new MeshStandardMaterial({ color: '#888888' });
    const at = (name: string, x: number) => {
      const node = new Group();
      node.name = name;
      node.position.x = x;
      // the mesh is a child of the GlobalId-named node, as GLTFLoader builds a multi-primitive node
      node.add(new Mesh(new BoxGeometry(1, 1, 1), shared));
      root.add(node);
      return node;
    };
    for (const [i, n] of ['A', 'B', 'C', 'D', 'E'].entries()) at(n, i * 2);
    root.updateMatrixWorld(true);
    return { root, shared };
  }
  const mat = (root: Object3D, name: string) =>
    (root.getObjectByName(name)?.children[0] as Mesh).material as MeshStandardMaterial;

  it('M3-13 colours by role (first role wins), removed half-transparent, the rest dimmed; originals kept', () => {
    const { root, shared } = house();
    const shown = highlight(
      root,
      [
        { global_id: 'A', role: 'moved' },
        { global_id: 'B', role: 'removed' },
        { global_id: 'C', role: 'affected' },
        { global_id: 'A', role: 'added' },
        { global_id: 'X', role: 'affected' },
      ],
      COLOURS,
    );
    expect(shown.counts).toEqual({ moved: 1, removed: 1, affected: 1 });
    expect(shown.missing).toBe(1);
    expect(shown.box?.min.x).toBeCloseTo(-0.5);
    expect(shown.box?.max.x).toBeCloseTo(4.5);
    expect(mat(root, 'A').color.getHexString()).toBe('0000ff');
    expect(mat(root, 'A').opacity).toBe(1);
    expect(mat(root, 'B').color.getHexString()).toBe('ff0000');
    expect(mat(root, 'B').opacity).toBe(0.5);
    expect(mat(root, 'C').color.getHexString()).toBe('ff8800');
    for (const n of ['D', 'E']) {
      expect(mat(root, n).opacity).toBe(0.12);
      expect(mat(root, n).transparent).toBe(true);
      expect(mat(root, n).depthWrite).toBe(false);
    }
    expect(shared.color.getHexString()).toBe('888888');
    expect(shared.opacity).toBe(1);
  });

  it('M3-13 nothing listed or nothing found: nothing changes', () => {
    const { root, shared } = house();
    expect(highlight(root, [], COLOURS)).toEqual({ counts: {}, missing: 0, box: null });
    expect(highlight(root, [{ global_id: 'X', role: 'moved' }], COLOURS)).toEqual({
      counts: {},
      missing: 1,
      box: null,
    });
    expect(mat(root, 'A')).toBe(shared);
  });
});

describe('focusBox', () => {
  const whole = new Box3(new Vector3(0, 0, 0), new Vector3(20, 6, 10));
  const distance = (box: Box3) => {
    const camera = new PerspectiveCamera(45, 16 / 9);
    return camera.position.distanceTo(frame(camera, box));
  };

  it('M3-14 one small element: centred on it, never framed tighter than half the whole model', () => {
    const door = new Box3(new Vector3(1, 0, 1), new Vector3(2, 2.1, 1.2));
    const box = focusBox(door, whole);
    expect(box.getCenter(new Vector3()).distanceTo(door.getCenter(new Vector3()))).toBeLessThan(
      1e-9,
    );
    const half = new Box3().setFromCenterAndSize(new Vector3(), new Vector3(10, 3, 5));
    expect(distance(box)).toBeGreaterThanOrEqual(distance(half) - 1e-9);
    expect(distance(box)).toBeGreaterThan(distance(door) * 3);
  });

  it('M3-14 a highlight larger than half the model keeps its own size', () => {
    const wing = new Box3(new Vector3(0, 0, 0), new Vector3(18, 6, 9));
    expect(focusBox(wing, whole).equals(wing)).toBe(true);
  });
});
