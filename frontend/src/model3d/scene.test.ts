import { Box3, Frustum, Matrix4, PerspectiveCamera, Vector3 } from 'three';
import { describe, expect, it } from 'vitest';
import { frame } from './scene';

describe('scene', () => {
  it('M3-15 frame puts the whole box in view with the target at its centre', () => {
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
