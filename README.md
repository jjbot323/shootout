# 8/29 Golf

Live net better-ball scoring for a 16-player one-round match. Static site,
Firebase Realtime Database for shared state — every phone sees every score
within a fraction of a second, no logins.

## Layout

    index.html              the whole site, generated — do not hand-edit
    src/template.html       the real source (UI + scoring logic)
    src/build-site.py       template.html -> ../index.html, swapping in the Firebase layer
    src/firebase-config.json   web config (gitignored; see below)
    src/verify.py           independent Python model of the scoring, diffed against the page
    src/build.py            builds the self-contained Claude Artifact variant

## Rebuilding

    cd src && python build-site.py

## Firebase config

`src/firebase-config.json` holds the web config object:

    { "apiKey": "...", "authDomain": "...", "databaseURL": "...", "projectId": "...",
      "appId": "..." }

Without it the site still runs, but shows "Offline" and keeps scores on the
device only. The build embeds it into index.html at build time.

## Scoring

26 points: four 2v2 net better-ball matches at 4 each (front 9, back 9, and 2
for the 18), plus team aggregate 4, low net 2, low gross 2, birdie count 2.
Handicaps are the adjusted numbers as given — used directly, not normalised to
scratch, so the low man still receives his strokes.
