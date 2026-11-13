# Junction 2025 Top 5 stage pitch: LoreDash

- Video: https://www.youtube.com/watch?v=43uQE6cZGXU
- Junction 2025 (main), 2nd overall, Supercell challenge, solo. Stage pitch plus jury Q&A, 8:15.
- Source: YouTube auto-generated English captions, fetched 2026-11-10 with yt-dlp. Machine transcription: names, numbers and technical terms may be wrong; check against the video before quoting. Timestamps are approximate paragraph starts.

---

[0:00] Our next team coming to present is Law Dash. &gt;&gt; Let's give a round of applause for them as they come on the stage. &gt;&gt; All right. Sorry for the issues. Uh the sound is not working, but I'm going to hold the mic to the speakers. So, let's see how it sounds. &gt;&gt; More curiosity sparks. Hi, I'm Frank and this is my project uh Lore Dash or Curiosity Sparks Games.

[0:34] This is for the Supercell Challenge and again my name is Frank and my team's name is to be Frank. Um, I'd like to know how many people here this is a a familiar concept. The random button on Wikipedia. You click on it, you start somewhere and few hours go and you end up on a completely different place. Uh, you can start off at an old Ford

[1:08] Fiesta and you end up at Quantum Chromodnamics or something like that. Um, but that's just because you're curious. Uh, it's a good thing. Uh, you're just curious about the world, all the weird little things that exist. But the question is, as you're sitting there going through all those articles, does any of it stick necessarily? Um, you're just reading. It's all very ir relevant. You're reading about a small river in south of Muldova. Might not stick

[1:40] because you're it's just another river really. Um so gamified learning uh has been coming up lately. Uh you all heard about Cahoot quizzing platform from Norway. Uh Dualingo of course. Um I hope I don't use up the time. The counter is not going. Oh yeah, Dolingo of course. Um Minecraft has an educational edition. uh geogesser which is more towards esports now but it's educational as well. You

[2:14] learn about different places in the world. Uh so could we just turn random articles into games maybe as you can see there uh we just learned

[2:52] about a small region in Colombia uh publication about genomics research and as you can see there uh you got a description how to play the game as well as a short educational story and if you're interested you can click on the link can read a bit and then go back to your sort of miniame loop uh that Lord Dash provides. And Lord Dash is built using of course Wikipedia. Uh thank you Wikipedia. We all love you. So we fetch a random article and we generate a game plan at

[3:26] first using Gemini. Um you're an expert game programmer. Uh figure out a good fun educational game for this. Um, and then generate which assets do you need, which bit map sound effects, and then [snorts] of course it uses the Gemini Pro later on to generate an actual JavaScript uh loop which renders to a canvas. Um, and then also we use 11 Labs uh to generate some nice old school sound effects to go along with the game. And you might be thinking, Game Boy

[4:00] graphics, wow, 67, as the kids say, or 67. That just shows how old I am. I can't even say it. Um, of course, I'm I'm I'm turning 32. I'm a bit nostalgic for these sort of graphics. Um, and also, you know, it's a hackathon. What can you do in this time? uh but it proves a concept and on a short such short time you can build uh such a generator that simply turns random Wikipedia articles into fun learning experiences

[4:33] with some proper work. This could easily take on the likes of Geogesser and and Dolingo. Um, which could even render 3D graphics and even bring a more interactive, maybe make the games a bit bigger, not so small. Um, so that could be a future potential for this. And almost the coolest part of this whole thing uh is Gemini's LIA live experimental API which uh Lord Dash implements to great effect if I may say so myself of course now hope you can

[5:08] hear this. So, as I'm generating this game now, you'll hear the music dynamically change. [music] &gt;&gt; It's live. Yeah, we'll show it later if we Okay, so yeah, it's live. Uh, it's live on this URL. I was going to show it, but I guess I'm out of time. But uh you can use that QR code if you want to go and

[5:40] generate the game for yourself. Uh there's also the dash cache with pre-made games that you can go and access. &gt;&gt; Thank you. [applause] &gt;&gt; This is really cool. Um I'm I'm curious as you were using uh as you were using so many different models to kind of piece together the games themselves. Um, which models did you use and why? Like you mentioned LIA real time, I think you

[6:12] mentioned 2.5 Pro. Why did you select those? &gt;&gt; Yeah, at first uh I was using Gemini 2.5 Flash for everything. So, first there's a prompt to create the general outline. It returns a JSON, a structured one, one with a plan of the game, one with how to play it, one with a list of assets, one with a list of sound effects. uh and then it the then it goes to a a parallel loop to generate the assets and then it goes to Gemini 2.5 Pro to generate the actual code because I found that you know it 2.5 flash it did make games also

[6:45] flat faster but you know there was quite a few runtime crashes so I switched to to pro and that worked quite well &gt;&gt; generation &gt;&gt; ah that was u uh actually I started off with Gemini there, but I I needed transparent sprites. So, I had to switch to Open AI at some point for that, but I would have used it, but needed the transparency. &gt;&gt; So, as a solo hacker, I'm assuming solo hacker. &gt;&gt; Sorry. &gt;&gt; You're a solo hacker. &gt;&gt; Oh, yeah. Yeah. &gt;&gt; What What was the hardest part of this

[7:17] process for you in the past 72 hours as a solo hacker? &gt;&gt; Uh, well, &gt;&gt; this morning I got up at 6:00. &gt;&gt; Got up? &gt;&gt; Yeah. I went to sleep at 4 in the hotel. uh came here at six o'clock and then the crunch time before the 10:00 am uh deadline. That was definitely the hardest part. All this presentation and the most of the editing was done this morning. So definitely crunch time when you don't have anybody to rely on. Uh so &gt;&gt; and then real last question. The the thing you just showed was that actually live generating the game then or is that just recorded?

[7:49] &gt;&gt; Yeah, that that in the pres. Yeah. So uh if we go here, here it is. Okay. &gt;&gt; I like this one about crocodile dundee building on the go. All right. Thank you so much, Lord Dash. Give another hand. [applause]
