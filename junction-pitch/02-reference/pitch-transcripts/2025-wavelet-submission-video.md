# Junction 2025 submission video: Wavelet

- Video: https://www.youtube.com/watch?v=ZBChAesXt1Q
- Junction 2025 (main), 1st overall. The team's 2-minute submission video, 2:00.
- Source: YouTube auto-generated English captions, fetched 2026-11-10 with yt-dlp. Machine transcription: names, numbers and technical terms may be wrong; check against the video before quoting. Timestamps are approximate paragraph starts.

---

[0:02] We just spent the last 24 hours building a rendering engine in pure C++ and OpenGL. Why? Cuz we're insane. If you want to see the coolest graphics you've ever seen, stick around. We're currently doing the sensor fusion radio city challenge where using the provided 3D model of Hong Kong, demonstrate how radio travel, place imaginary moving radio sources [music] on the map. For example, There's no single correct solution for this challenge. There are multiple

[0:34] creative ways of showing your results. &gt;&gt; But we did 10 times more than that. [music] &gt;&gt; Okay, you get the gist. We built a radio wave simulator. But here's how we did it. To get an accurate mathematical model to simulate our radio waves, all sources seem to point towards the helm's equations, which see tend to do everything in one go and one time step, but it's really, really slow and difficult to compute. But soon we found the Maxwell equations, which can do everything in time step after time step,

[1:06] kind of like what we do in a simulation. We did some OpenGL and pure C++ testing to get some initial drafts and eventually optimized to get a full-on shader based C++ implementation. One of the first things we implemented after importing the model was a coloring system since we only wanted to render vertices that were actually useful to us. The next thing that we implemented after that was focusing on uh getting the maxel equation working with our Hong Kong model, the one that you saw earlier with the cube. Um beyond that it was mostly optimization. So you can see this quite large grid that scales with ON

[1:38] cubed which um the way we handle that is with dynamic grids which tries to fit as many transmitter nodes as possible in one grid. Hey, banger. I love that.
