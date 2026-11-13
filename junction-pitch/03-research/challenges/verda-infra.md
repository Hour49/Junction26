# Verda: what their infrastructure gives us

- Date: 2026-11-13 19:55 (Helsinki) · Author: Bogdan's Claude orchestrator
- Question: what does Verda (formerly DataCrunch, Helsinki GPU cloud, owner of the AI Infrastructure track) provide,
  and what of it fits our build?
- Answer in one line: GPUs by the hour in Helsinki, plus two things we can use in 48 h without running servers: an
  OpenAI-compatible inference API with two vision-capable open models, and serverless containers for our own model.
  Everything runs in Finland, which answers Stoa's EU-only rule.

All facts are Verda's own claims from [verda.com/pricing](https://verda.com/pricing),
[/gpu-instances](https://verda.com/gpu-instances), [/inference](https://verda.com/inference),
[/serverless-containers](https://verda.com/serverless-containers) and
[docs.verda.com](https://docs.verda.com/resources/services-overview/) (services overview, inference, containers,
locations, billing), read 2026-11-13 ~19:50. They are **reported**, single-source; prices change often (third-party
lists from August and early November show different numbers).

## Products

| Product | What it is | Fits a 48 h build? |
| --- | --- | --- |
| Verda Inference (labelled "preview") | Open-weight models through an OpenAI-compatible API (`https://inference.verda.com/v1`, `/chat/completions`), billed per token | **Yes**: one adapter, no servers |
| Serverless containers | Our own container image as an auto-scaling GPU endpoint, scales to zero, billed per replica-minute (shown in 10-minute steps); batch jobs for work over ~3 min | Yes, if we host our own model (an OCR or layout model) |
| GPU instances | VMs with 1, 2, 4 or 8 GPUs, on-demand or spot (spot about half price, can be stopped any second) | For experiments; we must stop them ourselves |
| CPU instances | AMD EPYC, from 4 vCPU | Only if we need a server |
| Instant clusters, bare metal, managed Kubernetes, Slurm | Multi-node training | No |
| Storage | NVMe block and shared filesystem ($0.20 per GiB-month), S3-compatible object storage (beta), container registry | Only with the above |
| Tooling | REST API, Python and Go SDKs, CLI, Terraform/OpenTofu, dstack, SkyPilot | |

## Inference models (per 1M tokens)

| Model | Input | Cached input | Output | Notes |
| --- | --- | --- | --- | --- |
| Kimi K3.1 Pro (`kimi-k3-1-pro`) | $2.00 | $0.20 | $10.00 | 1M context, text and image input, tool calling; reads "screenshots, charts and scanned documents" (their words) |
| DeepSeek V4.1 Flash (`deepseek-4-1-flash-1017`) | $0.15 | $0.006 | $0.60 | 1M context, text and image input, tool calling |
| GLM 5.3 | coming soon | | | text only |

The model panel on the inference page shows Kimi at $3.00 / $0.30 / $15.00, which contradicts the cards and the
pricing page: check before quoting a cost. No dedicated OCR or document model is listed. Prompts and responses are
not stored (in-memory cache, removed within 2 hours), not used for training and not shared with the model maker.

## GPU prices (USD per GPU-hour, pricing page)

| GPU | On-demand | Spot | Serverless on-demand |
| --- | --- | --- | --- |
| B300 268GB | 12.29 | 6.145 | 13.52 |
| B200 180GB | 9.414 | 4.707 | 10.36 |
| H200 141GB | 6.635 | 3.318 | 7.300 |
| H100 80GB | 5.189 | 2.595 | 5.710 |
| A100 80GB | 2.374 | 1.187 | n/a |
| RTX PRO 6000 96GB | 2.808 | 1.404 | 3.090 |
| L40S 48GB | 1.998 | 0.999 | 2.200 |
| RTX A6000 48GB | 0.879 | 0.4395 | n/a |

Also GB300, V100 and confidential-computing variants of B300, B200 and RTX PRO 6000.

## Data, location, billing

- Data centres: Helsinki only (FIN-01..03), renewable power (hydro and wind), PUE 1.2-1.3. Inference runs "in our
  datacenters in Europe".
- Claims SOC 2 Type II, C5, ISO 27001/27017/27018/27701 and GDPR compliance; 99.95% uptime. Trust centre:
  trust.verda.com.
- Prepaid balance, billed in 10-minute steps. At zero balance instances stop and volumes are deleted (restorable for
  96 hours). Inference needs a $1 balance to enable a model and pauses when the balance runs low.
- Credit coupons are given at events and hackathons and redeemed under "Billing & settings" in a project.

## What it means for us (assumed)

- **Stoa:** if their data must stay in the EU, Verda Inference with Kimi K3.1 Pro or DeepSeek V4.1 Flash reads
  scanned sheets inside Finland, behind the same adapter as Gemini. DeepSeek is cheap enough to run every page; Kimi
  for the hard ones. That also enters us in Verda's AI Infrastructure track.
- Keep it to the inference API, plus one serverless container only if a dedicated OCR model beats the vision LLMs
  on our golden set. No GPU instances to babysit.
- Set a spend cap in our adapter (docs/ENGINEERING.md §2.6): the balance is prepaid and resources stop at zero.

## Training or fine-tuning on Verda (Bogdan's question, 2026-11-13 20:05)

Compute is cheap and not the limit: a LoRA fine-tune of a ~7B open vision model on a few hundred examples, or a few
epochs of a pretrained detector, is roughly 1-3 GPU-hours on an H100 or A100 (estimate, not measured), so $5-15 on
demand and half on spot. The limits are labelled data and the team's hours.

Where training could beat a prompted model for Stoa (assumed until the golden set says so):
1. **Locating things on a floor plan** (walls, doors, rooms, symbols as coordinates). Stoa's app opens the floor plan
   at an issue's location, so findings need positions; general vision LLMs are weaker at exact positions on dense
   drawings than a trained detector. Public data: CubiCasa5K (5,000 annotated, mostly Finnish floor plans, 80+
   classes, [repo](https://github.com/CubiCasa/CubiCasa5k)) and FloorPlanCAD (15,663 CAD drawings, 30 symbol
   classes, [site](https://floorplancad.github.io)). **Both are CC BY-NC 4.0** (checked 2026-11-13): fine for a
   hackathon demo, not for a commercial Stoa pilot; never commit the data; declare it in the submission (Terms §8.2).
2. **Distilling a big model into a small one for title blocks:** Kimi or Gemini labels a few hundred sheets, we
   hand-check a sample, LoRA a small open vision model on Verda and serve it from a serverless container. The claim
   to prove: same accuracy on held-out sheets at a fraction of the cost, all in Finland. Needs Stoa's sheets first.

Not worth training: the gap and conflict checks (deterministic rules are cheaper and explainable), anything from
scratch, a general LLM fine-tune.

How (if we do it): baseline first (prompted model + 20-sheet golden set, Fri night); one person, time-boxed to the
first end-to-end run (Sat ~14:00); the model ships only if it beats the baseline on held-out sheets, behind the same
adapter so dropping it costs nothing. Spot GPUs with frequent checkpoints (spot can stop any second); stop instances
when done. Training script, config, seed and eval go in the repo; weights and data do not (the pre-commit hook
refuses files over 5 MB anyway).

## Questions for the Verda workshop (Fri 20:45, Loft)

- How much credit per team, how do we claim it, and does it cover Inference as well as GPUs?
- What does the AI Infrastructure track reward: cost, latency, open models, fine-tuning, use of serverless?
- Rate limits on Inference for hackathon accounts? Any model or OCR model coming this weekend?
- Cold start for serverless containers on L40S, roughly?
- Do the credits cover a few H100 or A100 hours for fine-tuning, and does the track reward training or fine-tuning?

## Open questions / UNVERIFIED

- Credit amount and track criteria (not on the site).
- Whether Inference is still "preview" with lower limits.
- The Kimi price conflict above.
