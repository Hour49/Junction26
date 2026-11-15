"""Train the line-style segmenter (smp U-Net, ResNet-18 encoder) on make_labels.py's clinic set.

    python train.py <train dir> <out dir> --minutes 25 [--pilot]

10 classes: 0 = no services line, 1..9 = the renderer's line palette (8 colours + other grey).
Crops 256 px at full resolution (lines are 2-4 px wide), 2/3 of them centred on a line pixel.
Augmentation for scans and photos: grey (p .35), Gaussian blur, salt, JPEG, contrast/brightness,
a light ramp, flips and 90 degree turns. One picture (clinic-plumbing Level_2 plumbing, all three
variants) is held back for the validation IoU of "line vs not" and of the palette class.
"""

import argparse
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from PIL import Image

CROP = 256
CLASSES = 10
VAL = "bsc-clinic_clinic-plumbing--Level_2--plumbing"


def load(root: Path):
    train, val = [], []
    for lbl in sorted(root.glob("*/*/*.lbl.png")):
        image = np.array(Image.open(str(lbl).replace(".lbl.png", ".png")).convert("RGB"))
        label = np.array(Image.open(lbl))
        lines = np.argwhere(label > 0)
        (val if lbl.name.startswith(VAL) else train).append((image, label, lines, lbl.parent.name))
    return train, val


def augment(img: np.ndarray, rng: random.Random) -> np.ndarray:
    if rng.random() < 0.35:
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        img = np.stack([g, g, g], axis=2)
    if rng.random() < 0.5:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.3, 1.6))
    f = img.astype(np.float32)
    f = (f - 128) * rng.uniform(0.7, 1.3) + 128 + rng.uniform(-40, 25)
    if rng.random() < 0.4:
        h, w = f.shape[:2]
        ramp = np.linspace(0, 1, w if rng.random() < 0.5 else h, dtype=np.float32)
        ramp = ramp[None, :, None] if len(ramp) == w else ramp[:, None, None]
        f = f * (1 - rng.uniform(0, 0.35) * ramp)
    if rng.random() < 0.5:
        f = f + np.random.normal(0, rng.uniform(1, 8), f.shape).astype(np.float32)
    img = np.clip(f, 0, 255).astype(np.uint8)
    if rng.random() < 0.4:
        salt = np.random.random(img.shape[:2]) < rng.uniform(0, 0.004)
        img[salt] = np.random.choice([0, 255], size=(int(salt.sum()), 1)).astype(np.uint8)
    if rng.random() < 0.5:
        _, enc = cv2.imencode(
            ".jpg", img[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, rng.randint(40, 90)]
        )
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)[..., ::-1]
    return np.ascontiguousarray(img)


class Crops(torch.utils.data.IterableDataset):
    def __init__(self, items, seed):
        self.items, self.seed = items, seed

    def __iter__(self):
        info = torch.utils.data.get_worker_info()
        rng = random.Random(self.seed + (info.id if info else 0) * 7919 + int(time.time()))
        np.random.seed(rng.randrange(2**31))
        weights = [1.0 + min(len(it[2]), 20000) / 2000 for it in self.items]
        while True:
            image, label, lines, _ = rng.choices(self.items, weights)[0]
            h, w = label.shape
            if len(lines) and rng.random() < 0.67:
                cy, cx = lines[rng.randrange(len(lines))]
                y0, x0 = cy - rng.randrange(CROP), cx - rng.randrange(CROP)
            else:
                y0, x0 = rng.randrange(max(1, h - CROP)), rng.randrange(max(1, w - CROP))
            y0, x0 = min(max(0, y0), max(0, h - CROP)), min(max(0, x0), max(0, w - CROP))
            img = image[y0 : y0 + CROP, x0 : x0 + CROP]
            lab = label[y0 : y0 + CROP, x0 : x0 + CROP]
            if img.shape[:2] != (CROP, CROP):
                pad = ((0, CROP - img.shape[0]), (0, CROP - img.shape[1]))
                img = np.pad(img, (*pad, (0, 0)), constant_values=255)
                lab = np.pad(lab, pad)
            img = augment(img, rng)
            k = rng.randrange(4)
            img, lab = np.rot90(img, k), np.rot90(lab, k)
            if rng.random() < 0.5:
                img, lab = img[:, ::-1], lab[:, ::-1]
            x = torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1).float() / 255.0
            yield (x - 0.5) / 0.25, torch.from_numpy(np.ascontiguousarray(lab)).long()


def model(encoder: str = "resnet18", weights: str | None = "imagenet") -> torch.nn.Module:
    return smp.Unet(encoder, encoder_weights=weights, classes=CLASSES)


@torch.no_grad()
def predict(net, image: np.ndarray, tile: int = 1024, pad: int = 64) -> np.ndarray:
    """Argmax class per pixel of a whole page, in overlapping tiles."""
    h, w = image.shape[:2]
    out = np.zeros((h, w), np.uint8)
    step = tile - 2 * pad
    for y in range(0, h, step):
        for x in range(0, w, step):
            y0, x0 = max(0, y - pad), max(0, x - pad)
            y1, x1 = min(h, y + step + pad), min(w, x + step + pad)
            crop = image[y0:y1, x0:x1]
            ph, pw = (-crop.shape[0]) % 32, (-crop.shape[1]) % 32
            crop = np.pad(crop, ((0, ph), (0, pw), (0, 0)), constant_values=255)
            t = torch.from_numpy(crop).permute(2, 0, 1).float()[None] / 255.0
            pred = net((t - 0.5) / 0.25)[0].argmax(0).numpy().astype(np.uint8)
            ys, xs = y - y0, x - x0
            hh, ww = min(step, h - y), min(step, w - x)
            out[y : y + hh, x : x + ww] = pred[ys : ys + hh, xs : xs + ww]
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("train", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--minutes", type=float, default=25)
    p.add_argument("--batch", type=int, default=24)
    p.add_argument("--workers", type=int, default=32)
    p.add_argument("--threads", type=int, default=64)
    p.add_argument("--encoder", default="resnet18")
    args = p.parse_args()
    torch.set_num_threads(args.threads)
    args.out.mkdir(parents=True, exist_ok=True)
    train, val = load(args.train)
    print("train", len(train), "val", len(val), flush=True)
    loader = torch.utils.data.DataLoader(
        Crops(train, 7), batch_size=args.batch, num_workers=args.workers, persistent_workers=True
    )
    net = model(args.encoder)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4)
    weight = torch.tensor([1.0] + [6.0] * (CLASSES - 1))
    end = time.time() + args.minutes * 60
    step, start = 0, time.time()
    for x, y in loader:
        net.train()
        logits = net(x)
        ce = F.cross_entropy(logits, y, weight=weight)
        prob_line = 1 - logits.softmax(1)[:, 0]
        line = (y > 0).float()
        dice = 1 - (2 * (prob_line * line).sum() + 1) / (prob_line.sum() + line.sum() + 1)
        loss = ce + dice
        opt.zero_grad()
        loss.backward()
        opt.step()
        step += 1
        for group in opt.param_groups:  # a cosine over the time budget (steps vary in speed)
            done = min(1.0, (time.time() - start) / (args.minutes * 60))
            group["lr"] = 1e-3 * (0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * done)))
        if step % 25 == 0:
            print(f"step {step} loss {loss.item():.4f} ce {ce.item():.4f} dice {dice.item():.4f}"
                  f" {time.time() - start:.0f}s", flush=True)  # fmt: skip
        if time.time() > end:
            break
    torch.save(net.state_dict(), args.out / "model.pt")
    (args.out / "encoder.txt").write_text(args.encoder)
    net.eval()
    for image, label, _, variant in val:
        pred = predict(net, image)
        a, b = pred > 0, label > 0
        iou = (a & b).sum() / max(1, (a | b).sum())
        cls = (pred[b] == label[b]).mean() if b.any() else float("nan")
        print(f"val {variant}: line IoU {iou:.3f}, palette right on truth line px {cls:.3f}")
    print("done", step, "steps", flush=True)


if __name__ == "__main__":
    main()
