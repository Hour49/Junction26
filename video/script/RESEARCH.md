# Research behind the script

Done 2026-11-14 by two research agents plus our repo. Sources accessed 2026-11-14. Anything a caption
or the voice-over says must come from this file or from a real measurement.

## Rules for what the video may claim

- The skit (act 1) is labelled "Dramatization" and its AI shots "AI-generated". The serious part (act 2)
  is a real screen recording, labelled "Real app, built this weekend". Reason: in 2025 the finalist
  Walkthrough opened with a concept video that "was not exactly our product", and the jury asked right
  away whether it was built that weekend (`junction-pitch/01-playbooks/pitching.md`).
- No absolute claims ("never wrong", "hallucination-free"). Legal AI tools sold as hallucination-free were
  wrong on more than 17% of queries (https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-queries).
  Show one real abstention and one real conflict instead.
- The video must work on mute: every spoken line is a burned-in caption. The deck embeds it silently, and
  audio failed for 2 of 5 finalists in 2025 (pitching.md).
- Total about 2:00 (every catalogued Junction submission video 2022-2025 runs about 2:00; 3:00 is the cap).
- Stoa already sells "answers from your project's own documents, with the source behind each one"
  (https://stoabuild.com). Their site makes no confidence, second-method, conflict, code-check or
  abstention claims, so those are what Vellum leads with. Their tone is plain; match it in act 2.

## Facts usable in the skit (Finland)

| Fact | Source |
| --- | --- |
| 1,719,650 of 3,124,286 Finnish dwellings have their own sauna (55%, 2020). "Missing a sauna" puts him in the other 45%. | https://stat.fi/til/asas/2020/01/asas_2020_01_2021-10-14_tau_005_en.html |
| About 3.2 million saunas in Finland (government, 2020). Other sources say 2.4-3.3 M, so avoid the exact count. | https://valtioneuvosto.fi/en/-/1410845/finland-s-sauna-culture-inscribed-on-unesco-intangible-cultural-heritage-list |
| An apartment owner must notify the housing company in writing before work that can affect its structures (Asunto-osakeyhtiölaki 1599/2009, ch. 5 §2); it may set conditions (§3). | https://www.finlex.fi/fi/lainsaadanto/2009/1599 |
| Espoo: a local wet-room change in a building over two storeys needs no contact with building control; a load-bearing change that needs new structural plans needs a permit. Rules differ by city (Mikkeli wants a permit for a new apartment sauna). Safe line: "check with rakennusvalvonta". | https://admin.espoo.fi/sites/default/files/2025-09/Liite%201.%20Rakenne-%20ja%20talotekniikan%20korjaukset%20ja%20muutokset_VERC.pdf , https://mikkeli.fi/wp-content/uploads/2025/10/Huoneistosaunan-luvanvaraisuus-2025.pdf |
| A sauna heater must be installed by an electrician with contracting rights (Tukes). | https://tukes.fi/kodin-sahkoturvallisuus/mita-sahkotoita-saan-tehda-itse |
| Wet-room floors must be waterproofed and slope to the drain (decree 782/2017 §28-29). Housing companies usually ask for a VTT-certified wet-room inspector; the decree itself does not require one. | https://data.finlex.fi/api/media/statute/56219/mainPdf/main.pdf |
| Heater clearances depend on the model: the app should say "per the heater manual", not a number. Sauna room sizes (1.2 x 1.5 m etc.) could not be verified: keep them off screen. | K-Rauta guide, retailer listings |
| Architectural floor plans do not reliably show which walls are load-bearing; the structural drawings (rakennesuunnitelmat) do. Concrete walls are load-bearing by default (housing company forms). Honest app line: "Probably a light partition. I can't prove it from this drawing." | Helsinki and Espoo guidance above, https://www.skh.fi/wp-content/uploads/2025/03/HuoneistonMuutostyolomake.pdf |
| New buildings: apartment entrance door at least 850 mm clear width, doors to living rooms at least 800 mm (accessibility decree 241/2017 §4). Applies to new builds, so phrase it as "new-build standard". | https://www.finlex.fi/api/media/statute/61314/mainPdf/main.pdf |

A tenant cannot do any of this without the landlord's consent; the skit treats him as the owner.

## What Vellum really does (for act 2)

From `docs/REQUIREMENTS.md` and the README key values (2026-11-13): reads drawings once (CAD, PDF, scans);
answers with numbered marks on the drawing plus file, page and box; states the counting rule
("an open doorway is not a door"); counts a second, independent way and shows both numbers where they
disagree; gives a confidence; refuses with a reason (no scale, no plan view, resolution too low); logs
cost per question. Checks against the building code are a key value but not built yet (2026-11-14):
act 2 shows them only if they exist by recording time.

## Promo craft

- First 5 s: a person on screen, several shots, the product in view; no music or logo flash
  (Google ABCD research, https://thinkwithgoogle.com/marketing-strategies/video/viewer-attention-for-youtube-ads).
- Skit shots about 1.5-2 s each; hold UI shots long enough to read the caption.
- Build each joke on a real pain point (Dollar Shave Club,
  https://www.entrepreneur.com/growing-a-business/how-a-dollar-shave-clubs-ad-went-viral/224282).
- The 2024 Junction winner credited an AI-generated video; the 2025 runner-up opened on a relatable habit
  and ran exactly 2:00 (https://www.youtube.com/watch?v=5_vU2JDTQjo).
